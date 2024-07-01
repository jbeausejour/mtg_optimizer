from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from celery_app import make_celery
from dotenv import load_dotenv
from logger import setup_logging
import logging
import os

logger = logging.getLogger(__name__)

load_dotenv()

# Initialize the database
db = SQLAlchemy()

def create_app():
    
    app = Flask(__name__, static_folder='static', template_folder='templates', instance_relative_config=True)
    CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.getenv('SQLALCHEMY_TRACK_MODIFICATIONS', 'False').lower() == 'true'
    app.config['DEBUG'] = os.getenv('DEBUG', 'False').lower() == 'true'
    app.config['CELERY_BROKER_URL'] = os.getenv('CELERY_BROKER_URL')
    app.config['CELERY_RESULT_BACKEND'] = os.getenv('CELERY_RESULT_BACKEND')
    
    print(f"FLASK_DEBUG environment variable: {os.getenv('FLASK_DEBUG')}")
    print(f"app.config['DEBUG']: {app.config['DEBUG']}")
    print(f"app.debug: {app.debug}")

    app.config.from_mapping(
        UPLOAD_FOLDER='uploads',
        ENV='development'
    )

    setup_logging(app)
    # Initialize the database with the app
    db.init_app(app)

    with app.app_context():
        db.create_all()

    migrate = Migrate(app, db)  # Initialize Flask-Migrate

    # Register blueprints using the function from routes.py
    from routes import register_blueprints
    register_blueprints(app)

    print(f"after")
    with app.app_context():
        @app.route('/')
        def index():
            logger.debug("Sending from template_folder")
            print("Sending from template_folder")
            return render_template('index.html')

        @app.route('/static/<path:path>')
        def send_static(path):
            print(f"after static")
            full_path = os.path.join(app.static_folder, path)
            app.logger.debug(f"Requested static file: {full_path}")
            app.logger.debug(f"Static folder: {app.static_folder}")
            app.logger.debug(f"Directory contents: {os.listdir(app.static_folder)}")
            if os.path.exists(full_path):
                app.logger.debug(f"File exists: {full_path}")
            else:
                app.logger.debug(f"File does not exist: {full_path}")
            return send_from_directory(app.static_folder, path)

    return app

if __name__ == '__main__':

    logger.debug("Running from main")
    print("Running from main", flush=True)
    app = create_app()
    print(f"after 2")
    celery = make_celery(app)
    print(f"after 3")
    with app.app_context():
        print(f"after 4")
        logger.debug("Starting Flask app")
        app.run(host='0.0.0.0', port=5000)  # Remove debug=True from here