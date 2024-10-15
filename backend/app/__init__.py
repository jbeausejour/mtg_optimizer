"""Backend init Module."""

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask

from config import get_config

from .extensions import init_extensions
from .tasks.celery_app import celery_app


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

    setup_logging(app)

    return app


def setup_logging(app):
    """Setup func"""
    # Configure the log level for the app
    app.logger.setLevel(logging.INFO)

    # Check if logs should be written to stdout
    if not app.debug and not app.testing:
        if app.config.get("LOG_TO_STDOUT"):
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.INFO)
            stream_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
                )
            )
            app.logger.addHandler(stream_handler)
        else:
            if not os.path.exists("logs"):
                os.mkdir("logs")
            file_handler = RotatingFileHandler(
                "logs/mtg_optimizer.log", maxBytes=10240, backupCount=10
            )
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
                )
            )
            app.logger.addHandler(file_handler)

    # Add a custom logger setup if needed
    logger = logging.getLogger("your_logger_name")
    logger.setLevel(logging.INFO)

    # Add file handler for the custom logger
    file_handler = RotatingFileHandler(
        "logs/custom_mtg_optimizer.log", maxBytes=10240, backupCount=10
    )
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
    )
    logger.addHandler(file_handler)

    # Add stream handler to custom logger
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        )
    )
    logger.addHandler(stream_handler)

    # Log the startup message
    app.logger.info("MTG Optimizer startup")
