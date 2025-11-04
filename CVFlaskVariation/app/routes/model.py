"""
Model information and blacklist management routes.
"""

import logging
from flask import Blueprint, jsonify, request
from ..services.yolo_detector import get_detector
from ..utils.filtering import is_class_blacklisted
from .. import constants

logger = logging.getLogger(__name__)

bp = Blueprint('model', __name__)


@bp.route('/get_classes')
def get_classes():
    """Get available object classes (excluding blacklisted ones)."""
    try:
        detector = get_detector()
        all_classes = list(detector.get_class_names().values())

        # Filter out blacklisted classes
        available_classes = [cls for cls in all_classes if not is_class_blacklisted(cls)]

        return jsonify({
            'classes': available_classes,
            'success': True,
            'total_classes': len(all_classes),
            'available_classes': len(available_classes),
            'blacklisted_classes': list(constants.BLACKLISTED_CLASSES)
        })
    except Exception as e:
        logger.error(f"Error getting classes: {e}")
        return jsonify({'error': str(e), 'success': False})


@bp.route('/model_info')
def model_info():
    """Get model information."""
    try:
        detector = get_detector()
        model_data = detector.get_model_info()

        all_classes = model_data.get('class_names', [])
        available_classes = [cls for cls in all_classes if not is_class_blacklisted(cls)]

        return jsonify({
            'model_loaded': model_data.get('loaded', False),
            'all_classes': all_classes,
            'available_classes': available_classes,
            'total_class_count': len(all_classes),
            'available_class_count': len(available_classes),
            'blacklisted_classes': list(constants.BLACKLISTED_CLASSES),
            'blacklisted_count': len(constants.BLACKLISTED_CLASSES),
            'success': True
        })
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        return jsonify({'error': str(e), 'success': False})


@bp.route('/blacklist', methods=['GET', 'POST'])
def manage_blacklist():
    """Manage the class blacklist."""
    if request.method == 'GET':
        return jsonify({
            'blacklisted_classes': list(constants.BLACKLISTED_CLASSES),
            'success': True
        })

    elif request.method == 'POST':
        try:
            data = request.get_json()
            action = data.get('action')
            class_name = data.get('class_name', '').lower()

            if action == 'add' and class_name:
                constants.BLACKLISTED_CLASSES.add(class_name)
                logger.info(f"Added '{class_name}' to blacklist")
                return jsonify({
                    'message': f"Added '{class_name}' to blacklist",
                    'blacklisted_classes': list(constants.BLACKLISTED_CLASSES),
                    'success': True
                })

            elif action == 'remove' and class_name:
                constants.BLACKLISTED_CLASSES.discard(class_name)
                logger.info(f"Removed '{class_name}' from blacklist")
                return jsonify({
                    'message': f"Removed '{class_name}' from blacklist",
                    'blacklisted_classes': list(constants.BLACKLISTED_CLASSES),
                    'success': True
                })

            elif action == 'set' and 'classes' in data:
                constants.BLACKLISTED_CLASSES = set(cls.lower() for cls in data['classes'])
                logger.info(f"Updated blacklist to: {list(constants.BLACKLISTED_CLASSES)}")
                return jsonify({
                    'message': 'Blacklist updated',
                    'blacklisted_classes': list(constants.BLACKLISTED_CLASSES),
                    'success': True
                })

            else:
                return jsonify({'error': 'Invalid action or missing class_name', 'success': False})

        except Exception as e:
            logger.error(f"Error managing blacklist: {e}")
            return jsonify({'error': str(e), 'success': False})
