"""
Camera management routes for overseer dashboard.
Handles camera registration, status updates, and communication.
"""

from flask import Blueprint, jsonify, request
from app.services.camera_registry import get_camera_registry
from app.services.server_monitor import get_monitor
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('cameras', __name__, url_prefix='/admin/cameras')


@bp.route('/register', methods=['POST'])
def register_camera():
    """Register a new camera client."""
    monitor = get_monitor()
    monitor.record_request()

    try:
        data = request.get_json() or {}
        camera_id = data.get('camera_id')

        # Get client info
        client_info = {
            'ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'Unknown'),
            'name': data.get('camera_name', f'Camera {camera_id[:8] if camera_id else "New"}')
        }

        registry = get_camera_registry()
        camera = registry.register_camera(camera_id=camera_id, client_info=client_info)

        return jsonify({
            'success': True,
            'camera_id': camera.camera_id,
            'camera': camera.to_dict(),
            'message': 'Camera registered successfully'
        })

    except Exception as e:
        logger.error(f"Error registering camera: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/unregister/<camera_id>', methods=['POST'])
def unregister_camera(camera_id: str):
    """Unregister a camera client."""
    monitor = get_monitor()
    monitor.record_request()

    try:
        registry = get_camera_registry()
        success = registry.unregister_camera(camera_id)

        if success:
            return jsonify({
                'success': True,
                'message': f'Camera {camera_id} unregistered'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Camera not found'
            }), 404

    except Exception as e:
        logger.error(f"Error unregistering camera: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/heartbeat/<camera_id>', methods=['POST'])
def camera_heartbeat(camera_id: str):
    """Update camera heartbeat and state."""
    monitor = get_monitor()
    monitor.record_request()

    try:
        data = request.get_json() or {}
        registry = get_camera_registry()

        camera = registry.get_camera(camera_id)
        if not camera:
            return jsonify({
                'success': False,
                'error': 'Camera not found. Please register first.'
            }), 404

        # Update camera state
        registry.update_camera_state(camera_id, data)

        return jsonify({
            'success': True,
            'message': 'Heartbeat received',
            'camera': camera.to_dict()
        })

    except Exception as e:
        logger.error(f"Error processing heartbeat: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/list', methods=['GET'])
def list_cameras():
    """Get list of all registered cameras."""
    monitor = get_monitor()
    monitor.record_request()

    try:
        registry = get_camera_registry()

        # Cleanup stale cameras before listing
        registry.cleanup_stale_cameras()

        stats = registry.get_statistics()

        return jsonify({
            'success': True,
            'statistics': {
                'total_cameras': stats['total_cameras'],
                'online_cameras': stats['online_cameras'],
                'offline_cameras': stats['offline_cameras'],
                'total_detections': stats['total_detections'],
                'total_frames': stats['total_frames']
            },
            'cameras': stats['cameras']
        })

    except Exception as e:
        logger.error(f"Error listing cameras: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<camera_id>', methods=['GET'])
def get_camera(camera_id: str):
    """Get detailed information about a specific camera."""
    monitor = get_monitor()
    monitor.record_request()

    try:
        registry = get_camera_registry()
        camera = registry.get_camera(camera_id)

        if not camera:
            return jsonify({
                'success': False,
                'error': 'Camera not found'
            }), 404

        return jsonify({
            'success': True,
            'camera': camera.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting camera: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<camera_id>/command', methods=['POST'])
def send_camera_command(camera_id: str):
    """
    Send a command to a specific camera.
    Commands: start_detection, stop_detection, toggle_audio, toggle_pathfinding
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        data = request.get_json() or {}
        command = data.get('command')
        params = data.get('params', {})

        registry = get_camera_registry()
        camera = registry.get_camera(camera_id)

        if not camera:
            return jsonify({
                'success': False,
                'error': 'Camera not found'
            }), 404

        # Store command for camera to poll
        # In a real implementation, this would use WebSocket to push to camera
        # For now, we just log it
        logger.info(f"Command '{command}' sent to camera {camera_id} with params: {params}")

        return jsonify({
            'success': True,
            'message': f'Command {command} sent to camera {camera_id}',
            'command': command,
            'params': params
        })

    except Exception as e:
        logger.error(f"Error sending command: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<camera_id>/message', methods=['POST'])
def send_message_to_camera(camera_id: str):
    """
    Send a text/audio message to a specific camera.
    This will be announced via TTS on the camera.
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        data = request.get_json() or {}
        message = data.get('message')

        if not message:
            return jsonify({
                'success': False,
                'error': 'Message text is required'
            }), 400

        registry = get_camera_registry()
        camera = registry.get_camera(camera_id)

        if not camera:
            return jsonify({
                'success': False,
                'error': 'Camera not found'
            }), 404

        # In real implementation, push message via WebSocket
        logger.info(f"Message sent to camera {camera_id}: {message}")

        return jsonify({
            'success': True,
            'message': 'Message sent successfully',
            'camera_id': camera_id,
            'text': message
        })

    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/broadcast', methods=['POST'])
def broadcast_message():
    """
    Broadcast a message to all online cameras.
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        data = request.get_json() or {}
        message = data.get('message')

        if not message:
            return jsonify({
                'success': False,
                'error': 'Message text is required'
            }), 400

        registry = get_camera_registry()
        online_cameras = registry.get_online_cameras()

        # In real implementation, push to all cameras via WebSocket
        logger.info(f"Broadcasting message to {len(online_cameras)} cameras: {message}")

        return jsonify({
            'success': True,
            'message': 'Message broadcast successfully',
            'recipients': len(online_cameras),
            'text': message
        })

    except Exception as e:
        logger.error(f"Error broadcasting message: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<camera_id>/stream', methods=['GET'])
def get_camera_stream(camera_id: str):
    """
    Get the latest frame from a camera for dashboard viewing.
    Returns base64 encoded JPEG frame.
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        registry = get_camera_registry()
        camera = registry.get_camera(camera_id)

        if not camera:
            return jsonify({
                'success': False,
                'error': 'Camera not found'
            }), 404

        # Check if streaming is enabled
        if not camera.dashboard_streaming_enabled:
            return jsonify({
                'success': True,
                'streaming_enabled': False,
                'message': 'Camera streaming is disabled by user'
            })

        # Get latest frame
        frame_data = camera.get_latest_frame()

        if frame_data:
            return jsonify({
                'success': True,
                'streaming_enabled': True,
                'frame': frame_data,
                'fps': camera.current_fps,
                'timestamp': camera.last_frame_time
            })
        else:
            return jsonify({
                'success': True,
                'streaming_enabled': True,
                'frame': None,
                'message': 'No frame available yet'
            })

    except Exception as e:
        logger.error(f"Error getting camera stream: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<camera_id>/upload_frame', methods=['POST'])
def upload_camera_frame(camera_id: str):
    """
    Upload a frame from the camera client for dashboard streaming.
    Camera clients should send frames periodically when streaming is enabled.
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        data = request.get_json() or {}
        frame_data = data.get('frame')

        if not frame_data:
            return jsonify({
                'success': False,
                'error': 'Frame data is required'
            }), 400

        registry = get_camera_registry()
        camera = registry.get_camera(camera_id)

        if not camera:
            return jsonify({
                'success': False,
                'error': 'Camera not found. Please register first.'
            }), 404

        # Store the frame
        camera.update_frame(frame_data)

        return jsonify({
            'success': True,
            'message': 'Frame uploaded successfully'
        })

    except Exception as e:
        logger.error(f"Error uploading frame: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<camera_id>/voice/start', methods=['POST'])
def start_voice_session(camera_id: str):
    """
    Start a voice communication session with a specific camera.
    This clears any existing audio queue and prepares for new voice chunks.
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        registry = get_camera_registry()
        camera = registry.get_camera(camera_id)

        if not camera:
            return jsonify({
                'success': False,
                'error': 'Camera not found'
            }), 404

        camera.start_voice_session()

        return jsonify({
            'success': True,
            'message': 'Voice session started',
            'camera_id': camera_id,
            'camera_name': camera.camera_name
        })

    except Exception as e:
        logger.error(f"Error starting voice session: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<camera_id>/voice/chunk', methods=['POST'])
def upload_voice_chunk(camera_id: str):
    """
    Upload a voice audio chunk to be played on the camera.
    Chunks should be sent in sequence with incrementing sequence numbers.
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        data = request.get_json() or {}
        audio_data = data.get('audio')
        sequence = data.get('sequence', 0)

        if not audio_data:
            return jsonify({
                'success': False,
                'error': 'Audio data is required'
            }), 400

        registry = get_camera_registry()
        camera = registry.get_camera(camera_id)

        if not camera:
            return jsonify({
                'success': False,
                'error': 'Camera not found'
            }), 404

        # Queue the audio chunk
        camera.queue_audio_chunk(audio_data, sequence)

        return jsonify({
            'success': True,
            'message': 'Audio chunk uploaded',
            'sequence': sequence,
            'queue_length': len(camera.audio_chunks_queue)
        })

    except Exception as e:
        logger.error(f"Error uploading voice chunk: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/<camera_id>/voice/stop', methods=['POST'])
def stop_voice_session(camera_id: str):
    """
    Stop a voice communication session with a specific camera.
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        registry = get_camera_registry()
        camera = registry.get_camera(camera_id)

        if not camera:
            return jsonify({
                'success': False,
                'error': 'Camera not found'
            }), 404

        camera.stop_voice_session()

        return jsonify({
            'success': True,
            'message': 'Voice session stopped',
            'camera_id': camera_id
        })

    except Exception as e:
        logger.error(f"Error stopping voice session: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/broadcast/voice/start', methods=['POST'])
def start_voice_broadcast():
    """
    Start a voice broadcast to all online cameras.
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        registry = get_camera_registry()
        online_cameras = registry.get_online_cameras()

        for camera in online_cameras:
            camera.start_voice_session()

        return jsonify({
            'success': True,
            'message': 'Voice broadcast started',
            'recipients': len(online_cameras)
        })

    except Exception as e:
        logger.error(f"Error starting voice broadcast: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/broadcast/voice/chunk', methods=['POST'])
def broadcast_voice_chunk():
    """
    Broadcast a voice audio chunk to all online cameras.
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        data = request.get_json() or {}
        audio_data = data.get('audio')
        sequence = data.get('sequence', 0)

        if not audio_data:
            return jsonify({
                'success': False,
                'error': 'Audio data is required'
            }), 400

        registry = get_camera_registry()
        online_cameras = registry.get_online_cameras()

        for camera in online_cameras:
            camera.queue_audio_chunk(audio_data, sequence)

        return jsonify({
            'success': True,
            'message': 'Audio chunk broadcast',
            'sequence': sequence,
            'recipients': len(online_cameras)
        })

    except Exception as e:
        logger.error(f"Error broadcasting voice chunk: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/broadcast/voice/stop', methods=['POST'])
def stop_voice_broadcast():
    """
    Stop voice broadcast to all cameras.
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        registry = get_camera_registry()
        online_cameras = registry.get_online_cameras()

        for camera in online_cameras:
            camera.stop_voice_session()

        return jsonify({
            'success': True,
            'message': 'Voice broadcast stopped',
            'recipients': len(online_cameras)
        })

    except Exception as e:
        logger.error(f"Error stopping voice broadcast: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
