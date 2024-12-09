"""Backend init Module."""

import logging
from logging.handlers import RotatingFileHandler

from flask import Flask

from config import get_config

from .extensions import init_extensions
from .tasks.celery_app import celery_app


# Color codes
RESET = "\033[0m"
RED = "\033[31m"
YELLOW = "\033[33m"
WHITE = "\033[37m"
BLUE = "\033[34m"


# Formatter for logs with color
class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        'DEBUG': BLUE,
        'INFO': WHITE,
        'WARNING': YELLOW,
        'ERROR': RED,
        'CRITICAL': RED,
    }

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelname, WHITE)
        levelname = f"{color}{record.levelname}{RESET}"
        record.levelname = levelname  # Overwrite the levelname with colored version
        return super().format(record)


def setup_logging(app):
    """Configure logging to prevent duplication"""
    # Remove any existing handlers to prevent duplication
    app.logger.handlers.clear()
    
    # Configure handler
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter('%(asctime)s - %(name)s - %(message)s'))
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    
    # Prevent propagation to root logger
    app.logger.propagate = False
    
    return app.logger


def create_app(config_class=get_config()):
    """App creation func"""
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
        instance_relative_config=True,
    )
    app.config.from_object(config_class)

    init_extensions(app)

    celery_app.conf.update(app.config)

    with app.app_context():
        from app.api.admin_routes import admin_routes
        from app.api.card_routes import card_routes

        app.register_blueprint(admin_routes, url_prefix='/api/v1')
        app.register_blueprint(card_routes, url_prefix='/api/v1')

    # Setup logging with duplicate prevention
    logger = setup_logging(app)
    logger.info("MTG Optimizer startup")

    return app
