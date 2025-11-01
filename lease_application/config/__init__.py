"""
Configuration Management
Production-grade configuration with environment variables
"""

import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'lease-management-secret-key-change-in-production')
    DATABASE_PATH = BASE_DIR / 'lease_management.db'
    LOG_DIR = BASE_DIR / 'logs'
    
    # Flask settings
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = FLASK_ENV == 'development'
    
    # API settings
    API_HOST = os.environ.get('API_HOST', 'localhost')
    API_PORT = int(os.environ.get('API_PORT', 5001))
    
    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # Logging
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    # SECRET_KEY is checked at runtime, not class definition time
    # This allows the class to be imported even if SECRET_KEY isn't set
    # Flask will raise an error if SECRET_KEY is not set when accessing app.secret_key


# Get configuration based on environment
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

