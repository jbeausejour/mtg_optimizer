from flask import Flask, send_from_directory, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

from dotenv import load_dotenv,find_dotenv
import logging
import os

logging.basicConfig(level=logging.DEBUG)

load_dotenv(find_dotenv())

# Initialize the database
db = SQLAlchemy()

def create_app():
    
    app = Flask(__name__, static_folder='static', template_folder='templates', instance_relative_config=True)
    CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})

    app.config['ENV'] = 'development'
    app.config['DEBUG'] = True
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
    #app.config['CELERY_BROKER_URL'] = os.getenv('CELERY_BROKER_URL')
    #app.config['CELERY_RESULT_BACKEND'] = os.getenv('CELERY_RESULT_BACKEND')

    app.logger.setLevel(logging.DEBUG)
    # Initialize the database with the app
    db.init_app(app)

    with app.app_context():
        db.create_all()

    migrate = Migrate(app, db)  # Initialize Flask-Migrate

    # Register blueprints using the function from routes.py
    from app.api.routes import register_blueprints
    register_blueprints(app)

    with app.app_context():
        @app.route('/')
        def index():
            #logger.debug("Sending from template_folder")
            print("Sending from template_folder", flush=True)
            return render_template('index.html')
        
        # Route for serving favicon
        @app.route('/favicon.ico')
        def favicon():
            return send_from_directory(app.static_folder, 'favicon.ico')

        @app.route('/static/<path:path>')
        def send_static(path):
            print(f"after static", flush=True)
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
