"""Backend init Module."""

import logging

from config import get_config
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager

from .extensions import init_extensions
from .logging_config import setup_logging


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

    jwt = JWTManager(app)

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, expired_token):
        return (
            jsonify({"msg": "Token has expired", "token_type": expired_token["type"]}),
            401,
        )

    from app.tasks.celery_instance import celery_app

    celery_app.conf.update(app.config)

    with app.app_context():
        from app.api.admin_routes import admin_routes
        from app.api.card_routes import card_routes

        app.register_blueprint(admin_routes, url_prefix="/api/v1")
        app.register_blueprint(card_routes, url_prefix="/api/v1")

    # Setup logging with duplicate prevention
    # Get the app logger
    app_logger = logging.getLogger("app")
    if not app_logger.handlers:
        console_handler, file_handler = setup_logging("logs/flask_app.log")
        app_logger.addHandler(console_handler)
        app_logger.addHandler(file_handler)
        app_logger.setLevel(logging.INFO)
        app_logger.propagate = False

    app_logger.info("MTG Optimizer startup")

    return app
