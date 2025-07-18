import os
import logging
from dotenv import load_dotenv


load_dotenv()

from .config import get_config
from quart import Quart, jsonify
from quart_cors import cors
from quart_jwt_extended import JWTManager
from .logging_config import setup_logging

from sqlalchemy.orm import declarative_base

# Use environment variable or default for Redis
redis_url = os.environ.get("REDIS_URL", "redis://192.168.68.15:6379/0")
redis_host = os.environ.get("REDIS_HOST", "192.168.68.15")

# Base class for SQLAlchemy models
Base = declarative_base()

# JWT setup
jwt = JWTManager()

# Determine CORS origins
cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
cors_origins = cors_origins.split(",") if "," in cors_origins else [cors_origins]


def create_app(config_class=get_config()):
    """App creation func"""
    app = Quart(
        __name__,
        static_folder="static",
        template_folder="templates",
        instance_relative_config=True,
    )

    app = cors(
        app,
        allow_origin=cors_origins,
        allow_credentials=True,
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )
    app.config.from_object(config_class)

    jwt.init_app(app)

    @jwt.expired_token_loader
    def expired_token_callback(expired_token):
        return (
            jsonify({"msg": "Token has expired", "token_type": expired_token["type"], "error": "token_expired"}),
            401,
        )

    from app.tasks.celery_instance import celery_app

    celery_app.conf.update(app.config)

    @app.before_serving
    async def load_blueprints():
        from app.api.admin_routes import admin_routes
        from app.api.card_routes import card_routes
        from app.api.optimization_routes import optimization_routes
        from app.api.scan_routes import scan_routes
        from app.api.site_routes import site_routes
        from app.api.watchlist_routes import watchlist_routes

        app.register_blueprint(admin_routes, url_prefix="/api/v1")
        app.register_blueprint(card_routes, url_prefix="/api/v1")
        app.register_blueprint(optimization_routes, url_prefix="/api/v1")
        app.register_blueprint(scan_routes, url_prefix="/api/v1")
        app.register_blueprint(site_routes, url_prefix="/api/v1")
        app.register_blueprint(watchlist_routes, url_prefix="/api/v1")

    @app.before_serving
    async def initialize_caches():
        from app.services.card_service import CardService

        logging.info("Initializing application caches...")

        try:
            # Initialize card names cache
            card_cache_success = await CardService.initialize_card_names_cache()
            if card_cache_success:
                logging.info("✅ Card names cache initialized successfully")
            else:
                logging.error("❌ Failed to initialize card names cache")

            # Initialize sets cache if needed
            set_cache_success = await CardService.initialize_sets_cache()
            if set_cache_success:
                logging.info("✅ Sets names cache initialized successfully")
            else:
                logging.error("❌ Failed to initialize Sets names cache")

            logging.info("🚀 Application cache initialization complete")

        except Exception as e:
            logging.error(f"💥 Cache initialization failed: {str(e)}")

    # Setup logging with duplicate prevention
    # Get the app logger
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        console_handler, file_handler = setup_logging("logs/flask_app.log")
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.INFO)
        root_logger.propagate = False

    root_logger.info("MTG Optimizer startup")

    return app
