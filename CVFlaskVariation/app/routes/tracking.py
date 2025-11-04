"""
Object tracking management routes.
"""

import logging
import time
from flask import Blueprint, jsonify, session
from ..services.object_tracker import get_tracking_manager

logger = logging.getLogger(__name__)

bp = Blueprint('tracking', __name__)


@bp.route('/reset_tracking', methods=['POST'])
def reset_tracking():
    """Reset tracking for current session."""
    try:
        tracking_manager = get_tracking_manager()

        if 'session_id' in session:
            session_id = session['session_id']
            tracking_manager.reset_session(session_id)

            # Create new session ID
            session['session_id'] = str(time.time())

            return jsonify({
                'message': 'Tracking reset successfully',
                'success': True,
                'new_session_id': session['session_id']
            })
        else:
            return jsonify({
                'message': 'No active tracking session',
                'success': True
            })
    except Exception as e:
        logger.error(f"Error resetting tracking: {e}")
        return jsonify({'error': str(e), 'success': False})


@bp.route('/tracking_stats')
def tracking_stats():
    """Get tracking statistics for current session."""
    try:
        tracking_manager = get_tracking_manager()

        if 'session_id' not in session:
            global_stats = tracking_manager.get_global_stats()
            return jsonify({
                'active_tracks': 0,
                'total_sessions': global_stats['total_sessions'],
                'success': True
            })

        session_id = session['session_id']
        stats = tracking_manager.get_session_stats(session_id)
        global_stats = tracking_manager.get_global_stats()

        return jsonify({
            **stats,
            'total_sessions': global_stats['total_sessions'],
            'success': True
        })
    except Exception as e:
        logger.error(f"Error getting tracking stats: {e}")
        return jsonify({'error': str(e), 'success': False})
