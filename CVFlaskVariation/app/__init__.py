"""
Flask application factory for the blind navigation application.
"""

import logging
from flask import Flask
from flask_cors import CORS
from .config import get_config
from .services.yolo_detector import get_detector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(config_name=None):
    """
    Create and configure the Flask application.

    Args:
        config_name: Configuration environment name ('development', 'production', 'testing')

    Returns:
        Flask: Configured Flask application
    """
    app = Flask(__name__)

    # Load configuration
    config_class = get_config(config_name)
    app.config.from_object(config_class)

    # Initialize CORS
    CORS(app, resources={
        r"/*": {
            "origins": app.config['CORS_ORIGINS'],
            "methods": app.config['CORS_METHODS'],
            "allow_headers": app.config['CORS_ALLOW_HEADERS']
        }
    })

    # Initialize YOLO detector (singleton pattern)
    # This loads the model once when the app starts
    with app.app_context():
        logger.info("=" * 70)
        logger.info("🚀 Initializing YOLO Detector...")
        logger.info("=" * 70)

        detector = get_detector(
            model_path=app.config['MODEL_PATH'],
            force_cpu=app.config['FORCE_CPU']
        )

        model_info = detector.get_model_info()
        logger.info(f"✅ Detector initialized: {model_info.get('num_classes', 0)} classes loaded")
        logger.info(f"🎯 Device: {model_info.get('device', 'unknown')}")

    # Register blueprints
    from .routes import health, model, tracking, navigation, detection, cameras, client, dashboard

    app.register_blueprint(health.bp)
    app.register_blueprint(model.bp)
    app.register_blueprint(tracking.bp)
    app.register_blueprint(navigation.bp)
    app.register_blueprint(detection.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(cameras.bp)
    app.register_blueprint(client.bp)

    # Register error handlers
    @app.errorhandler(404)
    def not_found(error):
        from flask import jsonify
        return jsonify({'error': 'Endpoint not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        from flask import jsonify
        logger.error(f"Internal server error: {error}")
        return jsonify({'error': 'Internal server error'}), 500

    logger.info("=" * 70)
    logger.info("🦯 Flask Application Created Successfully")
    logger.info("=" * 70)

    return app


def log_startup_info(app):
    """
    Log application startup information.

    Args:
        app: Flask application instance
    """
    import torch
    from .constants import BLACKLISTED_CLASSES, CLASS_MAPPING
    from .services.yolo_detector import get_detector

    logger.info("=" * 70)
    logger.info("🚀 Starting YOLO11 Flask Application for Blind Navigation")
    logger.info("=" * 70)

    # GPU Status
    if torch.cuda.is_available():
        logger.info(f"🎮 GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"🎮 VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
        logger.info(f"✅ CUDA Version: {torch.version.cuda}")
    else:
        logger.warning("⚠️  NO GPU DETECTED - Using CPU (performance will be slower)")
        logger.warning("⚠️  For real-time blind navigation, GPU is highly recommended")

    # Model Info
    detector = get_detector()
    model_info = detector.get_model_info()
    logger.info(f"📦 Model classes available: {model_info.get('num_classes', 0)}")
    logger.info(f"🚫 Blacklisted classes: {len(BLACKLISTED_CLASSES)}")
    logger.info(f"🔄 Class mappings: {len(CLASS_MAPPING)} (e.g., man/woman → person)")

    # Endpoints
    logger.info("\n📡 Available endpoints:")
    logger.info("  🏠 / - Main application")
    logger.info("  🔍 /detect_image - Real-time object detection")
    logger.info("  💚 /health - Health check with GPU status")
    logger.info("  📊 /model_info - Model information")
    logger.info("  📋 /get_classes - Available object classes (filtered)")
    logger.info("  🚫 /blacklist - Manage class blacklist (GET/POST)")
    logger.info("  🎯 /reset_tracking - Reset object tracking (POST)")
    logger.info("  📈 /tracking_stats - Tracking statistics")
    logger.info("  🗺️  /calculate_path - Calculate navigation path (POST)")
    logger.info("  🖥️  /admin/dashboard - Server monitoring dashboard")
    logger.info("  📊 /admin/metrics - System metrics and performance")
    logger.info("  💚 /admin/health - Detailed health status")
    logger.info("  🔌 /admin/ping - Health ping")
    logger.info("  ⚠️  /admin/system/shutdown - Graceful server shutdown")

    logger.info("\n" + "=" * 70)
    logger.info("🦯 Optimized for REAL-TIME blind indoor navigation")
    logger.info("=" * 70 + "\n")
