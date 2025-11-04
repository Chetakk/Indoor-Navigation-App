"""
Health check and test routes.
"""

import logging
import time
import torch
from flask import Blueprint, render_template, jsonify
from ..services.yolo_detector import get_detector

logger = logging.getLogger(__name__)

bp = Blueprint('health', __name__)


@bp.route('/')
def index():
    """Render the main application page."""
    return render_template('index.html')


@bp.route('/test_connection', methods=['GET', 'POST'])
def test_connection():
    """Simple test endpoint to verify Flask → Frontend communication."""
    logger.info("🧪 Test connection endpoint called")
    response_data = {
        'success': True,
        'message': 'Flask backend is responding correctly',
        'timestamp': time.time(),
        'method': 'GET'  # Fixed - was using request.method
    }
    logger.info(f"📤 Sending test response: {response_data}")
    return jsonify(response_data)


@bp.route('/health')
def health_check():
    """Health check endpoint with GPU information."""
    detector = get_detector()
    model_info = detector.get_model_info()

    gpu_info = {}
    if torch.cuda.is_available():
        gpu_info = {
            'gpu_available': True,
            'gpu_name': torch.cuda.get_device_name(0),
            'gpu_memory_total_gb': round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2),
            'gpu_memory_allocated_gb': round(torch.cuda.memory_allocated(0) / 1024**3, 2),
            'gpu_memory_cached_gb': round(torch.cuda.memory_reserved(0) / 1024**3, 2),
            'device_in_use': model_info.get('device', 'cpu')
        }
    else:
        gpu_info = {
            'gpu_available': False,
            'device_in_use': 'cpu',
            'warning': 'No GPU detected - performance may be slower'
        }

    from ..constants import BLACKLISTED_CLASSES

    return jsonify({
        'status': 'healthy',
        'model_loaded': model_info.get('loaded', False),
        'model_classes': model_info.get('num_classes', 0),
        'model_name': 'YOLO11',
        'available_classes': model_info.get('class_names', [])[:10],  # Show first 10 classes
        'blacklisted_classes': list(BLACKLISTED_CLASSES),
        'blacklist_count': len(BLACKLISTED_CLASSES),
        **gpu_info
    })
