"""
Configuration settings for the USCIS Timeline Calculator application.

This module defines configuration classes for different environments:
- Development: For local development with debugging
- Testing: For automated testing
- Production: For deployment to production servers
"""

import os
import logging
from datetime import timedelta


class Config:
    """Base configuration class with settings common to all environments."""
    
    # Application settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    APP_NAME = 'USCIS Timeline Calculator'
    
    # Data update settings
    DATA_UPDATE_INTERVAL = timedelta(hours=6)  # Update processing times every 6 hours
    
    # Logging settings
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_LEVEL = logging.INFO
    
    # Scraping settings
    SCRAPING_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    SCRAPING_TIMEOUT = 15  # seconds
    
    # URLs
    USCIS_PROCESSING_TIMES_URL = 'https://egov.uscis.gov/processing-times/'
    
    # Database settings
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_NAME = os.environ.get('DB_NAME', 'uscis_calculator')
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '12345')
    
    @staticmethod
    def init_app(app):
        """Initialize application with this configuration."""
        pass


class DevelopmentConfig(Config):
    """Configuration for development environment."""
    DEBUG = True
    TESTING = False
    
    # Development specific settings
    FALLBACK_DATA_PATH = 'fallback_data_dev.json'
    CHARTS_FOLDER = 'static/charts_dev'
    
    # Database for development
    DB_NAME = os.environ.get('DB_NAME', 'uscis_calculator_dev')


class TestingConfig(Config):
    """Configuration for testing environment."""
    DEBUG = False
    TESTING = True
    
    # Testing specific settings
    FALLBACK_DATA_PATH = 'fallback_data_test.json'
    CHARTS_FOLDER = 'static/charts_test'
    
    # For faster testing
    DATA_UPDATE_INTERVAL = timedelta(minutes=1)
    
    # Database for testing
    DB_NAME = os.environ.get('DB_NAME', 'uscis_calculator_test')


class ProductionConfig(Config):
    """Configuration for production environment."""
    DEBUG = False
    TESTING = False
    
    # Production specific settings
    LOG_LEVEL = logging.WARNING
    FALLBACK_DATA_PATH = '/var/data/uscis_calculator/fallback_data.json'
    CHARTS_FOLDER = '/var/www/uscis_calculator/static/charts'
    
    # Production database
    DB_HOST = os.environ.get('DB_HOST', 'db.production.server')
    DB_NAME = os.environ.get('DB_NAME', 'uscis_calculator_prod')
    DB_USER = os.environ.get('DB_USER', 'uscis_app')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '12345')
    
    @staticmethod
    def init_app(app):
        """Additional production-specific initialization."""
        # Set up production loggers, etc.
        Config.init_app(app)
        
        # Configure production logging to file
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler('uscis_calculator.log',
                                          maxBytes=10485760,  # 10MB
                                          backupCount=10)
        file_handler.setFormatter(logging.Formatter(Config.LOG_FORMAT))
        file_handler.setLevel(Config.LOG_LEVEL)
        app.logger.addHandler(file_handler)


# Configuration dictionary mapping environment names to configuration classes
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}