"""
Object tracking service using DeepSORT.
"""

import logging
import time
import torch
from collections import defaultdict, deque
from deep_sort_realtime.deepsort_tracker import DeepSort
from ..constants import (
    TRACK_HISTORY_LENGTH,
    MAX_TRACKER_AGE,
    MIN_TRACK_INIT,
    NMS_MAX_OVERLAP,
    MAX_COSINE_DISTANCE,
    NN_BUDGET,
    USE_VISUAL_EMBEDDINGS
)

logger = logging.getLogger(__name__)


class ObjectTrackingManager:
    """Manages DeepSORT trackers for multiple sessions."""

    def __init__(self):
        """Initialize the tracking manager."""
        self.trackers = {}  # session_id -> DeepSort tracker
        self.track_histories = defaultdict(lambda: deque(maxlen=TRACK_HISTORY_LENGTH))
        self.session_last_activity = {}  # session_id -> timestamp
        self.session_timeout = 1800  # 30 minutes in seconds

    def get_tracker(self, session_id):
        """
        Get or create a tracker for a session.

        Args:
            session_id: Unique session identifier

        Returns:
            DeepSort: Tracker instance for this session
        """
        if session_id not in self.trackers:
            use_gpu = torch.cuda.is_available()

            # Try to create tracker with multiple fallback options
            tracker = None
            error_messages = []

            # Check if visual embeddings are enabled
            if not USE_VISUAL_EMBEDDINGS:
                # Fast mode: No embeddings, IoU-only tracking (10x faster)
                try:
                    tracker = DeepSort(
                        max_age=MAX_TRACKER_AGE,
                        n_init=MIN_TRACK_INIT,
                        nms_max_overlap=NMS_MAX_OVERLAP,
                        max_cosine_distance=MAX_COSINE_DISTANCE,
                        nn_budget=NN_BUDGET,
                        embedder=None,  # Disable embeddings for speed
                        half=False,
                        embedder_gpu=False
                    )
                    logger.info(f"Created tracker for session {session_id} (IoU-only mode, no embeddings)")
                except Exception as e:
                    error_messages.append(f"IoU-only mode failed: {str(e)}")
                    logger.warning(f"Failed to create IoU-only tracker: {e}")

            # Option 1: Try GPU with half precision (if embeddings enabled or fast mode failed)
            if tracker is None and use_gpu and USE_VISUAL_EMBEDDINGS:
                try:
                    tracker = DeepSort(
                        max_age=MAX_TRACKER_AGE,
                        n_init=MIN_TRACK_INIT,
                        nms_max_overlap=NMS_MAX_OVERLAP,
                        max_cosine_distance=MAX_COSINE_DISTANCE,
                        nn_budget=NN_BUDGET,
                        embedder="mobilenet",
                        half=True,
                        embedder_gpu=True
                    )
                    logger.info(f"Created tracker for session {session_id} (GPU + half precision)")
                except Exception as e:
                    error_messages.append(f"GPU+half failed: {str(e)}")
                    logger.warning(f"Failed to create GPU tracker with half precision: {e}")

            # Option 2: Try GPU without half precision
            if tracker is None and use_gpu and USE_VISUAL_EMBEDDINGS:
                try:
                    tracker = DeepSort(
                        max_age=MAX_TRACKER_AGE,
                        n_init=MIN_TRACK_INIT,
                        nms_max_overlap=NMS_MAX_OVERLAP,
                        max_cosine_distance=MAX_COSINE_DISTANCE,
                        nn_budget=NN_BUDGET,
                        embedder="mobilenet",
                        half=False,
                        embedder_gpu=True
                    )
                    logger.info(f"Created tracker for session {session_id} (GPU, no half precision)")
                except Exception as e:
                    error_messages.append(f"GPU failed: {str(e)}")
                    logger.warning(f"Failed to create GPU tracker: {e}")

            # Option 3: Fallback to CPU mode
            if tracker is None:
                try:
                    tracker = DeepSort(
                        max_age=MAX_TRACKER_AGE,
                        n_init=MIN_TRACK_INIT,
                        nms_max_overlap=NMS_MAX_OVERLAP,
                        max_cosine_distance=MAX_COSINE_DISTANCE,
                        nn_budget=NN_BUDGET,
                        embedder="mobilenet" if USE_VISUAL_EMBEDDINGS else None,
                        half=False,
                        embedder_gpu=False
                    )
                    mode = "with embeddings" if USE_VISUAL_EMBEDDINGS else "IoU-only"
                    logger.info(f"Created tracker for session {session_id} (CPU mode {mode})")
                except Exception as e:
                    error_messages.append(f"CPU failed: {str(e)}")
                    logger.error(f"Failed to create CPU tracker: {e}")
                    raise RuntimeError(f"Failed to create tracker with all options. Errors: {'; '.join(error_messages)}")

            self.trackers[session_id] = tracker

        return self.trackers[session_id]

    def update_tracks(self, session_id, detections, frame):
        """
        Update tracks for a session with new detections.

        Args:
            session_id: Unique session identifier
            detections: List of tuples (bbox_ltwh, confidence, class_name)
            frame: Current frame image (BGR)

        Returns:
            list: Confirmed track objects
        """
        # Update last activity timestamp for this session
        self.session_last_activity[session_id] = time.time()

        # Cleanup stale sessions periodically (every 100 requests)
        if len(self.session_last_activity) > 0 and len(self.session_last_activity) % 100 == 0:
            self.cleanup_stale_sessions()

        tracker = self.get_tracker(session_id)

        # If embeddings disabled, provide dummy embeddings for IoU-only tracking
        if not USE_VISUAL_EMBEDDINGS:
            import numpy as np
            # Add dummy embeddings (zeros) - not used for IoU tracking
            detections_with_embeddings = []
            for det in detections:
                # Format: (bbox, confidence, class_name, embedding)
                dummy_embedding = np.zeros(512)  # Dummy 512-d vector
                detections_with_embeddings.append((det[0], det[1], det[2], dummy_embedding))
            tracks = tracker.update_tracks(detections_with_embeddings, frame=frame)
        else:
            tracks = tracker.update_tracks(detections, frame=frame)

        # Filter to confirmed tracks only
        confirmed_tracks = [track for track in tracks if track.is_confirmed()]

        # Update track histories
        for track in confirmed_tracks:
            track_id = track.track_id
            ltrb = track.to_ltrb()

            # Calculate center point
            center_x = (ltrb[0] + ltrb[2]) / 2
            center_y = (ltrb[1] + ltrb[3]) / 2

            # Store position history
            track_key = f"{session_id}_{track_id}"
            self.track_histories[track_key].append((center_x, center_y))

        return confirmed_tracks

    def get_track_history(self, session_id, track_id):
        """
        Get the trajectory history for a specific track.

        Args:
            session_id: Unique session identifier
            track_id: Track identifier

        Returns:
            list: List of (x, y) positions
        """
        track_key = f"{session_id}_{track_id}"
        return list(self.track_histories.get(track_key, []))

    def reset_session(self, session_id):
        """
        Reset tracking for a session.

        Args:
            session_id: Unique session identifier
        """
        # Remove tracker for this session
        if session_id in self.trackers:
            del self.trackers[session_id]
            logger.info(f"Deleted tracker for session: {session_id}")

        # Clear track histories for this session
        keys_to_delete = [key for key in self.track_histories.keys()
                          if key.startswith(f"{session_id}_")]
        for key in keys_to_delete:
            del self.track_histories[key]

        # Remove last activity timestamp
        if session_id in self.session_last_activity:
            del self.session_last_activity[session_id]

        logger.info(f"Cleared {len(keys_to_delete)} track histories for session: {session_id}")

    def cleanup_stale_sessions(self):
        """
        Remove trackers and histories for sessions that haven't been active
        for more than session_timeout seconds. Prevents memory leaks.
        """
        current_time = time.time()
        stale_sessions = []

        # Find stale sessions
        for session_id, last_activity in list(self.session_last_activity.items()):
            if current_time - last_activity > self.session_timeout:
                stale_sessions.append(session_id)

        # Cleanup stale sessions
        for session_id in stale_sessions:
            logger.info(f"Cleaning up stale session: {session_id} (inactive for {self.session_timeout}s)")
            self.reset_session(session_id)

        if stale_sessions:
            logger.info(f"Cleaned up {len(stale_sessions)} stale session(s)")

        return len(stale_sessions)

    def get_session_stats(self, session_id):
        """
        Get tracking statistics for a session.

        Args:
            session_id: Unique session identifier

        Returns:
            dict: Session statistics
        """
        # Count active tracks for this session
        active_tracks = sum(1 for key in self.track_histories.keys()
                            if key.startswith(f"{session_id}_"))

        return {
            'session_id': session_id,
            'active_tracks': active_tracks,
            'has_tracker': session_id in self.trackers
        }

    def get_global_stats(self):
        """
        Get global tracking statistics.

        Returns:
            dict: Global statistics
        """
        return {
            'total_sessions': len(self.trackers),
            'total_tracked_objects': len(self.track_histories)
        }


# Global tracking manager instance (singleton)
_tracking_manager = None


def get_tracking_manager():
    """
    Get the global tracking manager instance (singleton).

    Returns:
        ObjectTrackingManager: The tracking manager instance
    """
    global _tracking_manager
    if _tracking_manager is None:
        _tracking_manager = ObjectTrackingManager()
    return _tracking_manager
