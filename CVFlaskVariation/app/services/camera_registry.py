"""
Camera registry service for managing connected cameras/clients.
Tracks camera status, metadata, and provides communication interface.
"""

import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class CameraClient:
    """Represents a connected camera/client."""

    def __init__(self, camera_id: str = None, client_info: Dict[str, Any] = None):
        """
        Initialize a camera client.

        Args:
            camera_id: Unique identifier for the camera (auto-generated if None)
            client_info: Client metadata (user agent, IP, etc.)
        """
        self.camera_id = camera_id or str(uuid.uuid4())
        self.connected_at = time.time()
        self.last_heartbeat = time.time()
        self.status = 'online'

        # Client metadata
        self.client_info = client_info or {}
        self.user_agent = self.client_info.get('user_agent', 'Unknown')
        self.ip_address = self.client_info.get('ip', 'Unknown')
        self.camera_name = self.client_info.get('name', f'Camera {self.camera_id[:8]}')

        # Camera state
        self.detection_active = False
        self.audio_enabled = False
        self.pathfinding_enabled = False
        self.dashboard_streaming_enabled = True  # Default to enabled

        # Statistics
        self.total_detections = 0
        self.total_frames = 0
        self.last_frame_time = None
        self.current_fps = 0

        # Battery info (if available from mobile devices)
        self.battery_level = None
        self.is_charging = None

        # Location info (if user enables geolocation)
        self.latitude = None
        self.longitude = None

        # Frame storage for dashboard streaming
        self.latest_frame = None  # Base64 encoded JPEG frame
        self.frame_timestamp = None

        # Voice communication
        self.audio_chunks_queue = []  # Queue of audio chunks to be played
        self.voice_session_active = False  # Whether operator is currently speaking
        self.voice_session_start = None  # When current voice session started
        self.last_audio_chunk_time = None  # Last time an audio chunk was received

        logger.info(f"Camera client created: {self.camera_id} ({self.camera_name})")

    def update_heartbeat(self):
        """Update last heartbeat timestamp."""
        self.last_heartbeat = time.time()
        if self.status == 'offline':
            self.status = 'online'
            logger.info(f"Camera {self.camera_id} back online")

    def update_status(self, status: str):
        """Update camera status."""
        old_status = self.status
        self.status = status
        if old_status != status:
            logger.info(f"Camera {self.camera_id} status changed: {old_status} -> {status}")

    def update_state(self, state_data: Dict[str, Any]):
        """Update camera state from client data."""
        if 'detection_active' in state_data:
            self.detection_active = state_data['detection_active']
        if 'audio_enabled' in state_data:
            self.audio_enabled = state_data['audio_enabled']
        if 'pathfinding_enabled' in state_data:
            self.pathfinding_enabled = state_data['pathfinding_enabled']
        if 'dashboard_streaming_enabled' in state_data:
            self.dashboard_streaming_enabled = state_data['dashboard_streaming_enabled']
        if 'total_detections' in state_data:
            self.total_detections = state_data['total_detections']
        if 'total_frames' in state_data:
            self.total_frames = state_data['total_frames']
        if 'fps' in state_data:
            self.current_fps = state_data['fps']
        if 'battery_level' in state_data:
            self.battery_level = state_data['battery_level']
        if 'is_charging' in state_data:
            self.is_charging = state_data['is_charging']
        if 'latitude' in state_data and 'longitude' in state_data:
            self.latitude = state_data['latitude']
            self.longitude = state_data['longitude']

        self.last_frame_time = time.time()
        self.update_heartbeat()

    def update_frame(self, frame_data: str):
        """
        Update the latest frame for dashboard streaming.

        Args:
            frame_data: Base64 encoded JPEG frame
        """
        self.latest_frame = frame_data
        self.frame_timestamp = time.time()

    def get_latest_frame(self) -> Optional[str]:
        """
        Get the latest frame for dashboard streaming.

        Returns:
            Base64 encoded JPEG frame or None if no frame available
        """
        # Return None if frame is too old (>2 seconds)
        if self.frame_timestamp and (time.time() - self.frame_timestamp) > 2:
            return None
        return self.latest_frame

    def start_voice_session(self):
        """Start a voice communication session."""
        self.voice_session_active = True
        self.voice_session_start = time.time()
        self.audio_chunks_queue = []  # Clear any old chunks
        logger.info(f"Voice session started for camera {self.camera_id}")

    def stop_voice_session(self):
        """Stop a voice communication session."""
        self.voice_session_active = False
        logger.info(f"Voice session stopped for camera {self.camera_id}")

    def queue_audio_chunk(self, audio_data: str, sequence: int):
        """
        Queue an audio chunk for playback.

        Args:
            audio_data: Base64 encoded audio data (WebM/Opus)
            sequence: Sequence number for ordering chunks
        """
        chunk = {
            'data': audio_data,
            'sequence': sequence,
            'timestamp': time.time()
        }
        self.audio_chunks_queue.append(chunk)
        self.last_audio_chunk_time = time.time()

        # Limit queue size to prevent memory issues (max 50 chunks ~ 10 seconds at 200ms chunks)
        if len(self.audio_chunks_queue) > 50:
            self.audio_chunks_queue.pop(0)

    def get_audio_chunks(self, last_sequence: int = -1) -> List[Dict[str, Any]]:
        """
        Get audio chunks after a given sequence number.

        Args:
            last_sequence: Last sequence number received by client

        Returns:
            List of audio chunks with sequence > last_sequence
        """
        # Filter chunks newer than last_sequence
        new_chunks = [chunk for chunk in self.audio_chunks_queue if chunk['sequence'] > last_sequence]

        # Clean up old processed chunks (older than 5 seconds)
        current_time = time.time()
        self.audio_chunks_queue = [
            chunk for chunk in self.audio_chunks_queue
            if current_time - chunk['timestamp'] < 5.0
        ]

        return new_chunks

    def clear_audio_queue(self):
        """Clear all queued audio chunks."""
        self.audio_chunks_queue = []
        logger.info(f"Audio queue cleared for camera {self.camera_id}")

    def is_voice_session_stale(self, timeout: int = 10) -> bool:
        """
        Check if voice session has been inactive for too long.

        Args:
            timeout: Timeout in seconds

        Returns:
            True if session is stale, False otherwise
        """
        if not self.voice_session_active:
            return False

        if self.last_audio_chunk_time is None:
            return False

        return (time.time() - self.last_audio_chunk_time) > timeout

    def get_uptime(self) -> float:
        """Get camera uptime in seconds."""
        return time.time() - self.connected_at

    def get_uptime_formatted(self) -> str:
        """Get formatted uptime string."""
        uptime = self.get_uptime()
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def is_stale(self, timeout: int = 30) -> bool:
        """Check if camera hasn't sent heartbeat within timeout seconds."""
        return (time.time() - self.last_heartbeat) > timeout

    def to_dict(self) -> Dict[str, Any]:
        """Convert camera info to dictionary."""
        return {
            'camera_id': self.camera_id,
            'camera_name': self.camera_name,
            'status': self.status,
            'connected_at': datetime.fromtimestamp(self.connected_at).isoformat(),
            'last_heartbeat': datetime.fromtimestamp(self.last_heartbeat).isoformat(),
            'uptime': self.get_uptime(),
            'uptime_formatted': self.get_uptime_formatted(),
            'detection_active': self.detection_active,
            'audio_enabled': self.audio_enabled,
            'pathfinding_enabled': self.pathfinding_enabled,
            'dashboard_streaming_enabled': self.dashboard_streaming_enabled,
            'total_detections': self.total_detections,
            'total_frames': self.total_frames,
            'current_fps': self.current_fps,
            'battery_level': self.battery_level,
            'is_charging': self.is_charging,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'voice_session_active': self.voice_session_active,
            'location': {
                'latitude': self.latitude,
                'longitude': self.longitude
            } if self.latitude and self.longitude else None
        }


class CameraRegistry:
    """Registry for managing all connected cameras."""

    def __init__(self):
        self.cameras: Dict[str, CameraClient] = {}
        self.stale_timeout = 30  # seconds
        logger.info("Camera registry initialized")

    def register_camera(self, camera_id: str = None, client_info: Dict[str, Any] = None) -> CameraClient:
        """
        Register a new camera or return existing one.

        Args:
            camera_id: Unique camera identifier
            client_info: Client metadata

        Returns:
            CameraClient: The registered camera client
        """
        if camera_id and camera_id in self.cameras:
            # Camera already registered, update heartbeat
            camera = self.cameras[camera_id]
            camera.update_heartbeat()
            logger.info(f"Camera {camera_id} reconnected")
            return camera

        # Create new camera
        camera = CameraClient(camera_id=camera_id, client_info=client_info)
        self.cameras[camera.camera_id] = camera
        logger.info(f"New camera registered: {camera.camera_id} (Total cameras: {len(self.cameras)})")
        return camera

    def unregister_camera(self, camera_id: str) -> bool:
        """
        Unregister a camera.

        Args:
            camera_id: Camera identifier

        Returns:
            bool: True if camera was unregistered, False if not found
        """
        if camera_id in self.cameras:
            camera = self.cameras.pop(camera_id)
            logger.info(f"Camera unregistered: {camera_id} (Total cameras: {len(self.cameras)})")
            return True
        return False

    def get_camera(self, camera_id: str) -> Optional[CameraClient]:
        """Get camera by ID."""
        return self.cameras.get(camera_id)

    def get_all_cameras(self) -> List[CameraClient]:
        """Get list of all cameras."""
        return list(self.cameras.values())

    def get_online_cameras(self) -> List[CameraClient]:
        """Get list of online cameras."""
        return [cam for cam in self.cameras.values() if cam.status == 'online' and not cam.is_stale(self.stale_timeout)]

    def get_offline_cameras(self) -> List[CameraClient]:
        """Get list of offline cameras."""
        return [cam for cam in self.cameras.values() if cam.status == 'offline' or cam.is_stale(self.stale_timeout)]

    def update_camera_state(self, camera_id: str, state_data: Dict[str, Any]) -> bool:
        """
        Update camera state.

        Args:
            camera_id: Camera identifier
            state_data: State data to update

        Returns:
            bool: True if updated, False if camera not found
        """
        camera = self.get_camera(camera_id)
        if camera:
            camera.update_state(state_data)
            return True
        return False

    def cleanup_stale_cameras(self):
        """Mark stale cameras as offline."""
        for camera in self.cameras.values():
            if camera.is_stale(self.stale_timeout) and camera.status != 'offline':
                camera.update_status('offline')

    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        all_cameras = self.get_all_cameras()
        online_cameras = self.get_online_cameras()
        offline_cameras = self.get_offline_cameras()

        total_detections = sum(cam.total_detections for cam in all_cameras)
        total_frames = sum(cam.total_frames for cam in all_cameras)

        return {
            'total_cameras': len(all_cameras),
            'online_cameras': len(online_cameras),
            'offline_cameras': len(offline_cameras),
            'total_detections': total_detections,
            'total_frames': total_frames,
            'cameras': [cam.to_dict() for cam in all_cameras]
        }


# Global registry instance
_registry = None


def get_camera_registry() -> CameraRegistry:
    """Get the global camera registry instance."""
    global _registry
    if _registry is None:
        _registry = CameraRegistry()
    return _registry
