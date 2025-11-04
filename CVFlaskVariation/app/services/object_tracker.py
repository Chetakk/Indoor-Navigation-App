"""
Object tracking service using DeepSORT.
"""

import logging
import torch
from collections import defaultdict, deque
from deep_sort_realtime.deepsort_tracker import DeepSort
from ..constants import (
    TRACK_HISTORY_LENGTH,
    MAX_TRACKER_AGE,
    MIN_TRACK_INIT,
    NMS_MAX_OVERLAP,
    MAX_COSINE_DISTANCE,
    NN_BUDGET
)

logger = logging.getLogger(__name__)


class ObjectTrackingManager:
    """Manages DeepSORT trackers for multiple sessions."""

    def __init__(self):
        """Initialize the tracking manager."""
        self.trackers = {}  # session_id -> DeepSort tracker
        self.track_histories = defaultdict(lambda: deque(maxlen=TRACK_HISTORY_LENGTH))

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

            self.trackers[session_id] = DeepSort(
                max_age=MAX_TRACKER_AGE,
                n_init=MIN_TRACK_INIT,
                nms_max_overlap=NMS_MAX_OVERLAP,
                max_cosine_distance=MAX_COSINE_DISTANCE,
                nn_budget=NN_BUDGET,
                embedder="mobilenet",
                half=True,
                embedder_gpu=use_gpu
            )
            logger.info(f"Created new tracker for session: {session_id} (GPU: {use_gpu})")

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
        tracker = self.get_tracker(session_id)
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

        logger.info(f"Cleared {len(keys_to_delete)} track histories for session: {session_id}")

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
