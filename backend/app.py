from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import json
import os

# Initialize the database
db = SQLAlchemy()

def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates', instance_relative_config=True)
    CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})
    app.config.from_mapping(
        SECRET_KEY='your_secret_key',
        SQLALCHEMY_DATABASE_URI='sqlite:///site_data.db',
        UPLOAD_FOLDER='uploads',
        ENV='development',
        DEBUG=True
    )

    # Initialize the database with the app
    db.init_app(app)
    migrate = Migrate(app, db)  # Initialize Flask-Migrate

    # Load data from JSON and text files
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, 'data', 'config.json')
    with open(config_path) as config_file:
        config = json.load(config_file)

    # Import and register blueprints
    from views import views
    app.register_blueprint(views)
    with app.app_context():
        @app.route('/')
        def index():
            return send_from_directory(app.template_folder, 'index.html')

        @app.route('/static/<path:path>')
        def send_static(path):
            return send_from_directory(app.static_folder, path)

        @app.route('/api/cards', methods=['GET'])
        def get_cards():
            card_list_path = os.path.join(base_dir, 'data', 'card_list.txt')
            with open(card_list_path) as f:
                card_list = f.readlines()
            return jsonify([{"card": card.strip()} for card in card_list])

        @app.route('/api/sites', methods=['GET'])
        def get_sites():
            site_list_path = os.path.join(base_dir, 'data', 'site_list.txt')
            with open(site_list_path) as f:
                site_list = f.readlines()
            return jsonify([{"site": site.strip()} for site in site_list])

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
