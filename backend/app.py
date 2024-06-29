from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import json
import os
import logging

logger = logging.getLogger(__name__)


# Initialize the database
db = SQLAlchemy()

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates', instance_relative_config=True)
    CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})


    # Determine the absolute path to the database
    base_dir = os.path.abspath(os.path.dirname(__file__))
    database_path = os.path.join(base_dir, 'instance', 'site_data.db')

    app.config.from_mapping(
        SECRET_KEY='your_secret_key',
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{database_path}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER='uploads',
        ENV='development',
        DEBUG=True
    )

    # Initialize the database with the app
    db.init_app(app)

    with app.app_context():
        db.create_all()

    migrate = Migrate(app, db)  # Initialize Flask-Migrate

    # Load data from JSON and text files
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, 'data', 'config.json')
    with open(config_path) as config_file:
        config = json.load(config_file)

    # Register blueprints using the function from routes.py
    from routes import register_blueprints
    register_blueprints(app)

    with app.app_context():
        @app.route('/')
        def index():
            logger.debug("Sending from template_folder")
            print("Sending from template_folder")
            return render_template('index.html')

        @app.route('/static/<path:path>')
        def send_static(path):
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
    print("Running from main")
    app = create_app()
    with app.app_context():
        app.run(debug=True, host='0.0.0.0', port=5000)