"""
Client-side routes for camera/user devices.
These endpoints are called by the user's device to receive data from dashboard.
"""

from flask import Blueprint, jsonify, request, session
from app.services.camera_registry import get_camera_registry
from app.services.server_monitor import get_monitor
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('client', __name__, url_prefix='/client')


@bp.route('/voice/chunks', methods=['GET'])
def get_voice_chunks():
    """
    Get pending voice audio chunks for this camera.
    Camera clients poll this endpoint to receive voice messages from dashboard.
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        # Get camera_id from session
        camera_id = session.get('camera_id')
        if not camera_id:
            return jsonify({
                'success': False,
                'error': 'No camera_id in session. Please register first.'
            }), 401

        # Get last sequence from query params
        last_sequence = request.args.get('last_sequence', -1, type=int)

        registry = get_camera_registry()
        camera = registry.get_camera(camera_id)

        if not camera:
            return jsonify({
                'success': False,
                'error': 'Camera not found'
            }), 404

        # Get new audio chunks
        chunks = camera.get_audio_chunks(last_sequence)

        return jsonify({
            'success': True,
            'voice_session_active': camera.voice_session_active,
            'chunks': chunks,
            'chunk_count': len(chunks)
        })

    except Exception as e:
        logger.error(f"Error getting voice chunks: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/register_session', methods=['POST'])
def register_session():
    """
    Register a camera session.
    This creates a session-based camera_id for voice communication polling.
    """
    monitor = get_monitor()
    monitor.record_request()

    try:
        data = request.get_json() or {}
        camera_name = data.get('camera_name', 'User Camera')

        # Get or create camera_id
        if 'camera_id' not in session:
            # Create new camera in registry
            client_info = {
                'ip': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', 'Unknown'),
                'name': camera_name
            }

            registry = get_camera_registry()
            camera = registry.register_camera(client_info=client_info)
            session['camera_id'] = camera.camera_id
            logger.info(f"New camera session registered: {camera.camera_id}")
        else:
            camera_id = session['camera_id']
            registry = get_camera_registry()
            camera = registry.get_camera(camera_id)
            if camera:
                camera.update_heartbeat()
            logger.info(f"Existing camera session: {camera_id}")

        return jsonify({
            'success': True,
            'camera_id': session['camera_id'],
            'message': 'Session registered'
        })

    except Exception as e:
        logger.error(f"Error registering session: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
