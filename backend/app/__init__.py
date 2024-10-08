from flask import Flask
from config import get_config
from .extensions import init_extensions
from .tasks.celery_app import celery_app
from logging.handlers import RotatingFileHandler
import logging
import os

def create_app(config_class=get_config()):
    app = Flask(__name__, static_folder='static', template_folder='templates', instance_relative_config=True)
    app.config.from_object(config_class)

    init_extensions(app)
    
    celery_app.conf.update(app.config)

    with app.app_context():
        from .api.routes import register_blueprints
        register_blueprints(app)

    setup_logging(app)

    return app

def setup_logging(app):
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