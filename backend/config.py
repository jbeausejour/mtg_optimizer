import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Secret key for Flask sessions and other security features
    SECRET_KEY = 'your_secret_key'  # Replace with a strong, random key

    # Database configuration
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(basedir, 'instance', 'site_data.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT configuration
    JWT_SECRET_KEY = 'your-jwt-secret-key-here'  # Replace with a different strong, random key
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # Redis
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # API configuration
    API_TITLE = 'MTG Optimizer API'
    API_VERSION = 'v1'
    OPENAPI_VERSION = '3.0.2'
    OPENAPI_URL_PREFIX = '/'
    OPENAPI_SWAGGER_UI_PATH = '/swagger-ui'
    OPENAPI_SWAGGER_UI_URL = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist/'

    # Scryfall API configuration
    SCRYFALL_API_URL = 'https://api.scryfall.com'

    # Logging configuration
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT')

    # Email configuration (if you're using email functionality)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['your-email@example.com']  # Replace with your admin email(s)

    # Optimization task config
    LOG_LEVEL_FILE = 'INFO'
    LOG_LEVEL_CONSOLE = 'INFO'
    SPECIAL_SITE_FLAG = True
    MILP_STRAT = True
    HYBRID_STRAT = False
    NSGA_ALGO_STRAT = False
    MIN_STORE = 1
    FIND_MIN_STORE = False
    
    # Scan retention config
    SCAN_RETENTION_DAYS = 30

class DevelopmentConfig(Config):
    DEBUG = True
    # Add any development-specific settings here

class ProductionConfig(Config):
    DEBUG = False
    # Add any production-specific settings here

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # Add any testing-specific settings here

# You can add more configuration classes as needed

# Set the active configuration
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    config_name = os.environ.get('FLASK_ENV', 'default')
    return config[config_name]