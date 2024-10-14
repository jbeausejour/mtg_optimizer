import logging

from flask import Blueprint

from .card_routes import card_routes
from .data_management_routes import data_management_routes
from .main_routes import main_routes
from .optimization_routes import optimization_routes
from .scan_routes import scan_routes
from .settings_routes import settings_routes
from .site_routes import site_routes

logger = logging.getLogger(__name__)


def register_blueprints(app):
    api = Blueprint("api", __name__, url_prefix="/api/v1")

    blueprints = [
        optimization_routes,
        data_management_routes,
        settings_routes,
        card_routes,
        site_routes,
        scan_routes,
        main_routes,
    ]

    for blueprint in blueprints:
        try:
            api.register_blueprint(blueprint)
            logger.debug(f"Registered blueprint: {blueprint.name}")
        except Exception as e:
            logger.error(
                f"Failed to register blueprint {blueprint.name}: {str(e)}")

    try:
        app.register_blueprint(api)
        logger.info("API Blueprint registered with prefix '/api/v1'")
    except Exception as e:
        logger.error(f"Failed to register API blueprint: {str(e)}")
