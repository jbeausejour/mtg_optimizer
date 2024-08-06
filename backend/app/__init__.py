from flask import Flask
from flask_cors import CORS
from logging.handlers import RotatingFileHandler
from config import get_config
from .extensions import db, migrate, jwt
from .tasks.celery_app import make_celery
from .tasks import CeleryConfig

import logging
import os

def create_app(config_class=get_config()):
    app = Flask(__name__, template_folder='templates', instance_relative_config=True)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app)

    CeleryConfig.init_app(app)
    
    # Initialize Celery
    celery = make_celery(app)
    app.extensions['celery'] = celery

    # Register blueprints
    from .api.routes import register_blueprints
    register_blueprints(app)

    # Setup logging
    if not app.debug and not app.testing:
        if app.config.get('LOG_TO_STDOUT'):
            app.logger.addHandler(logging.StreamHandler())
        else:
            if not os.path.exists('logs'):
                os.mkdir('logs')
            file_handler = RotatingFileHandler('logs/mtg_optimizer.log', maxBytes=10240, backupCount=10)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
            app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('MTG Optimizer startup')
    return app

# Import models after create_app to avoid circular imports
from . import models