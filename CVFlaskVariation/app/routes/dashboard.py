"""
Dashboard routes for server monitoring and control.
"""
from flask import Blueprint, render_template, jsonify, request
from app.services.server_monitor import get_monitor
from app.services.yolo_detector import get_detector
from app.services.object_tracker import get_tracking_manager
from app import constants
import logging
import os
import signal

logger = logging.getLogger(__name__)

bp = Blueprint('dashboard', __name__, url_prefix='/admin')


@bp.route('/dashboard')
def dashboard():
    """Render the server dashboard page."""
    return render_template('dashboard.html')


@bp.route('/voice-test')
def voice_test():
    """Render the voice call test page for diagnostics."""
    return render_template('voice_test.html')


@bp.route('/ping', methods=['GET'])
def ping():
    """Simple health ping endpoint."""
    monitor = get_monitor()
    monitor.record_request()

    return jsonify({
        'status': 'ok',
        'timestamp': monitor.get_health_status()['timestamp']
    })


@bp.route('/health', methods=['GET'])
def health():
    """Get detailed health status."""
    monitor = get_monitor()
    monitor.record_request()

    return jsonify(monitor.get_health_status())


@bp.route('/metrics', methods=['GET'])
def metrics():
    """Get all system metrics."""
    logger.info("Dashboard metrics endpoint called")
    monitor = get_monitor()
    monitor.record_request()

    try:
        all_metrics = monitor.get_all_metrics()
        logger.info("Metrics retrieved successfully")
        return jsonify(all_metrics)
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        raise


@bp.route('/metrics/cpu', methods=['GET'])
def cpu_metrics():
    """Get CPU metrics only."""
    monitor = get_monitor()
    monitor.record_request()

    return jsonify(monitor.get_cpu_metrics())


@bp.route('/metrics/memory', methods=['GET'])
def memory_metrics():
    """Get memory metrics only."""
    monitor = get_monitor()
    monitor.record_request()

    return jsonify(monitor.get_memory_metrics())


@bp.route('/metrics/gpu', methods=['GET'])
def gpu_metrics():
    """Get GPU metrics only."""
    monitor = get_monitor()
    monitor.record_request()

    return jsonify(monitor.get_gpu_metrics())


@bp.route('/metrics/performance', methods=['GET'])
def performance_metrics():
    """Get performance metrics only."""
    monitor = get_monitor()
    monitor.record_request()

    return jsonify(monitor.get_performance_stats())


@bp.route('/metrics/network', methods=['GET'])
def network_metrics():
    """Get network metrics only."""
    monitor = get_monitor()
    monitor.record_request()

    return jsonify(monitor.get_network_metrics())


@bp.route('/metrics/disk', methods=['GET'])
def disk_metrics():
    """Get disk metrics only."""
    monitor = get_monitor()
    monitor.record_request()

    return jsonify(monitor.get_disk_metrics())


@bp.route('/tracking/stats', methods=['GET'])
def tracking_stats():
    """Get tracking statistics."""
    monitor = get_monitor()
    monitor.record_request()

    try:
        tracking_manager = get_tracking_manager()
        stats = tracking_manager.get_stats()

        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error getting tracking stats: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/tracking/reset', methods=['POST'])
def reset_tracking():
    """Reset tracking statistics."""
    monitor = get_monitor()
    monitor.record_request()

    try:
        tracking_manager = get_tracking_manager()
        tracking_manager.reset_tracking()

        return jsonify({
            'success': True,
            'message': 'Tracking reset successfully'
        })
    except Exception as e:
        logger.error(f"Error resetting tracking: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/model/info', methods=['GET'])
def model_info():
    """Get model information."""
    monitor = get_monitor()
    monitor.record_request()

    try:
        detector = get_detector()
        if detector is None:
            return jsonify({
                'success': False,
                'error': 'Model not loaded'
            }), 500

        return jsonify({
            'success': True,
            'model': {
                'type': 'YOLOv8',
                'classes': len(detector.class_names),
                'class_names': detector.class_names,
                'device': str(detector.device),
                'blacklisted_classes': list(constants.BLACKLISTED_CLASSES)
            }
        })
    except Exception as e:
        logger.error(f"Error getting model info: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/system/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the server gracefully."""
    monitor = get_monitor()
    monitor.record_request()

    # Get optional delay parameter
    data = request.get_json() or {}
    delay = data.get('delay', 0)

    logger.info(f"Shutdown requested with {delay}s delay")

    try:
        # Return response before shutting down
        response = jsonify({
            'success': True,
            'message': f'Server shutting down in {delay} seconds',
            'uptime': monitor.get_uptime_formatted()
        })

        # Schedule shutdown
        if delay > 0:
            import threading
            def delayed_shutdown():
                import time
                time.sleep(delay)
                logger.info("Executing delayed shutdown")
                os.kill(os.getpid(), signal.SIGINT)

            threading.Thread(target=delayed_shutdown, daemon=True).start()
        else:
            # Immediate shutdown
            import threading
            def immediate_shutdown():
                import time
                time.sleep(0.5)  # Give time for response to be sent
                logger.info("Executing immediate shutdown")
                os.kill(os.getpid(), signal.SIGINT)

            threading.Thread(target=immediate_shutdown, daemon=True).start()

        return response

    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")
        monitor.record_error()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/system/restart', methods=['POST'])
def restart():
    """Restart the server (requires external process manager)."""
    monitor = get_monitor()
    monitor.record_request()

    logger.warning("Restart requested - note that restart requires external process manager")

    return jsonify({
        'success': False,
        'message': 'Restart requires external process manager (e.g., systemd, supervisor)',
        'hint': 'Use shutdown endpoint and restart manually or via process manager'
    }), 501


@bp.route('/logs/recent', methods=['GET'])
def recent_logs():
    """Get recent log entries (if available)."""
    monitor = get_monitor()
    monitor.record_request()

    # This is a placeholder - actual implementation would read from log files
    return jsonify({
        'success': True,
        'logs': [],
        'message': 'Log retrieval not yet implemented'
    })


@bp.errorhandler(404)
def dashboard_not_found(e):
    """Handle 404 errors in dashboard routes."""
    monitor = get_monitor()
    monitor.record_error()
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404


@bp.errorhandler(500)
def dashboard_server_error(e):
    """Handle 500 errors in dashboard routes."""
    monitor = get_monitor()
    monitor.record_error()
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500
