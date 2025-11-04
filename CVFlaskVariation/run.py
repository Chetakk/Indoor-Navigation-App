"""
Application entry point for the blind navigation Flask application.

Usage:
    python run.py

Environment Variables:
    FLASK_ENV: 'development', 'production', or 'testing' (default: 'development')
    FLASK_HOST: Host address (default: from config)
    FLASK_PORT: Port number (default: from config)
    SSL_CERT: Path to SSL certificate (default: 'cert.pem')
    SSL_KEY: Path to SSL key (default: 'key.pem')
"""

import os
from app import create_app, log_startup_info

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    # Log startup information
    log_startup_info(app)

    # Get configuration from app config
    host = app.config.get('HOST', '10.190.36.242')
    port = app.config.get('PORT', 5000)
    debug = app.config.get('DEBUG', False)
    use_ssl = app.config.get('USE_SSL', True)

    # SSL context
    ssl_context = None
    if use_ssl:
        ssl_cert = app.config.get('SSL_CERT', 'cert.pem')
        ssl_key = app.config.get('SSL_KEY', 'key.pem')

        # Check if SSL files exist
        if os.path.exists(ssl_cert) and os.path.exists(ssl_key):
            ssl_context = (ssl_cert, ssl_key)
            print(f"🔒 SSL enabled with cert: {ssl_cert}")
        else:
            print(f"⚠️  SSL files not found ({ssl_cert}, {ssl_key}), running without SSL")

    # Run the application
    print(f"\n🌐 Starting server on {host}:{port}")
    print(f"🔧 Debug mode: {'ON' if debug else 'OFF'}")
    print(f"🔒 SSL: {'ENABLED' if ssl_context else 'DISABLED'}")
    print("\n" + "=" * 70 + "\n")

    app.run(
        debug=debug,
        threaded=True,
        host=host,
        port=port,
        use_reloader=False,  # Disable reloader to avoid model loading twice
        ssl_context=ssl_context
    )
