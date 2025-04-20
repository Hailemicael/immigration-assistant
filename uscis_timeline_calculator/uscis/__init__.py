"""
USCIS Timeline Calculator package initialization.

This module initializes the Flask application using the application factory pattern,
configures the application, and registers blueprints.
"""

import os
import logging
from threading import Thread
from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from config import config

# Import services for initialization
from uscis.services.scraping import update_processing_data
import uscis.services.timeline as timeline_service
from uscis.services.database import get_db_connection, close_db_connection, init_db


def create_app(config_name):
    """
    Application factory function to create and configure the Flask application.
    
    Args:
        config_name: The name of the configuration to use (development, testing, production)
        
    Returns:
        A configured Flask application instance
    """
    # Create the Flask application instance
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Configure logging
    logging.basicConfig(
        level=app.config['LOG_LEVEL'],
        format=app.config['LOG_FORMAT']
    )
    
    # Enable CORS for API endpoints
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Configure proxy settings for production environments
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    
    # Ensure necessary directories exist
    os.makedirs(app.config['CHARTS_FOLDER'], exist_ok=True)
    
    # Register blueprints
    from uscis.routes import main as main_blueprint
    from uscis.routes import api as api_blueprint
    
    app.register_blueprint(main_blueprint)
    app.register_blueprint(api_blueprint, url_prefix='/api')
    
    # Configure database
    app.teardown_appcontext(close_db_connection)
    
    # Initialize application with data
    with app.app_context():
        # Initialize database schema
        init_db()
        
        # Update processing data
        update_processing_data()
    
    # Start background thread for periodic data updates
    if not app.config['TESTING']:
        def start_background_thread():
            """Start background thread for periodic data updates."""
            import time
            
            while True:
                # Sleep for the configured update interval
                time.sleep(app.config['DATA_UPDATE_INTERVAL'].total_seconds())
                
                # Update processing data
                with app.app_context():
                    try:
                        update_processing_data()
                    except Exception as e:
                        app.logger.error(f"Error updating processing data: {e}")
        
        # Start the background thread as a daemon thread
        thread = Thread(target=start_background_thread, daemon=True)
        thread.start()
    
    return app