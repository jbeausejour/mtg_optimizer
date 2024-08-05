from flask import Flask, send_from_directory, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from logging.handlers import RotatingFileHandler
from celery import Celery
from config import get_config

import logging
import os

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
celery = Celery(__name__)

def create_app(config_class=get_config()):
    app = Flask(__name__, static_folder='static', template_folder='templates', instance_relative_config=True)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    CORS(app)

    app.config['CELERY_BROKER_URL'] = f"sqlite:///{os.path.join(app.instance_path, 'celery-broker.sqlite').replace('\\', '/')}"
    app.config['CELERY_RESULT_BACKEND'] = f"sqlite:///{os.path.join(app.instance_path, 'celery-results.sqlite').replace('\\', '/')}"

    # Initialize Celery
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask

    # Register blueprints
    from app.api.routes import register_blueprints
    register_blueprints(app)

    # Register routes
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(app.static_folder, 'favicon.ico')

    @app.route('/static/<path:path>')
    def send_static(path):
        return send_from_directory(app.static_folder, path)

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

# Import models and tasks
from app import models
from app.tasks import optimization_tasks
