"""
Flask application configuration.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration."""

    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'VerySecretKey'

    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')
    CORS_METHODS = ['GET', 'POST', 'OPTIONS']
    CORS_ALLOW_HEADERS = ['Content-Type']

    # Model settings
    # NOTE: .env file overrides these defaults. Set MODEL_PATH=yolov8n-oiv7.engine for TensorRT
    MODEL_PATH = os.environ.get('MODEL_PATH', 'yolov8x-oiv7.engine')  # Default to TensorRT for best performance
    FORCE_CPU = os.environ.get('FORCE_CPU', 'false').lower() == 'true'  # Use GPU by default if available (RTX 5060)

    # Server settings
    HOST = os.environ.get('FLASK_HOST', '10.20.95.214')
    # HOST = os.environ.get('FLASK_HOST', '10.242.173.242')
    PORT = int(os.environ.get('FLASK_PORT', 5000))
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    # SSL settings
    SSL_CERT = os.environ.get('SSL_CERT', 'cert.pem')
    SSL_KEY = os.environ.get('SSL_KEY', 'key.pem')
    USE_SSL = os.environ.get('USE_SSL', 'true').lower() == 'true'

    # Accessibility settings for blind users
    BLIND_MODE_ENABLED = os.environ.get('BLIND_MODE_ENABLED', 'true').lower() == 'true'
    AUTO_START_DETECTION = os.environ.get('AUTO_START_DETECTION', 'true').lower() == 'true'
    VOICE_COMMANDS_ENABLED = os.environ.get('VOICE_COMMANDS_ENABLED', 'true').lower() == 'true'
    AUDIO_FEEDBACK_ENABLED = os.environ.get('AUDIO_FEEDBACK_ENABLED', 'true').lower() == 'true'

    # Audio settings for visually impaired users
    SPEECH_RATE = float(os.environ.get('SPEECH_RATE', '1.0'))  # Speech rate (0.5 to 2.0)
    SPEECH_PITCH = float(os.environ.get('SPEECH_PITCH', '1.0'))  # Speech pitch (0.0 to 2.0)
    SPEECH_VOLUME = float(os.environ.get('SPEECH_VOLUME', '1.0'))  # Volume (0.0 to 1.0)

    # Detection announcement settings
    ANNOUNCE_DELAY_MS = int(os.environ.get('ANNOUNCE_DELAY_MS', '3000'))  # Delay between announcements
    ANNOUNCE_PRIORITY_THRESHOLD = float(os.environ.get('ANNOUNCE_PRIORITY_THRESHOLD', '0.7'))  # Min confidence
    ANNOUNCE_COLLISION_WARNINGS = os.environ.get('ANNOUNCE_COLLISION_WARNINGS', 'true').lower() == 'true'


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    # Inherit FORCE_CPU from parent Config (respects .env file)


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # In production, you might want to enable GPU if available
    FORCE_CPU = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    FORCE_CPU = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """
    Get configuration based on environment.

    Args:
        env: Environment name ('development', 'production', 'testing')
             If None, uses FLASK_ENV environment variable or 'default'

    Returns:
        Config: Configuration class
    """
    if env is None:
        env = os.environ.get('FLASK_ENV', 'default')
    return config.get(env, config['default'])
