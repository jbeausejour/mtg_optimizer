import logging

from app.models.user import User
from app.services.admin_service import AdminService
from app.utils.create_user import create_user
from app.utils.load_initial_data import load_all_data, truncate_tables
from app.utils.validators import validate_setting_key, validate_setting_value
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

# Admin Routes
admin_routes = Blueprint("admin_routes", __name__)


# Settings Operations
@admin_routes.route("/settings", methods=["GET"])
@jwt_required()
def get_settings():
    logger.info("Getting all settings")
    settings = AdminService.get_all_settings()
    return jsonify([setting.to_dict() for setting in settings])


@admin_routes.route("/settings", methods=["POST"])
@jwt_required()
def update_settings():
    data = request.json
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid data"}), 400

    updated_settings = []
    for key, value in data.items():
        if not validate_setting_key(key) or not validate_setting_value(value):
            return jsonify({"error": f"Invalid setting key or value: {key}"}), 400

        setting = AdminService.update_setting(key, value)
        updated_settings.append(setting.to_dict())
        current_app.logger.info(f"Setting updated: {key}")

    return jsonify(updated_settings), 200


@admin_routes.route("/login", methods=["POST"])
def login():
    data = request.json
    current_app.logger.info(f"Login attempt for user: {data.get('username')}")

    user = User.query.filter_by(username=data["username"]).first()
    if user and user.check_password(data["password"]):
        access_token = create_access_token(identity=user.id)
        current_app.logger.info(f"Login successful for user: {user.username}")
        return jsonify(access_token=access_token, userId=user.id), 200  # Return userId

    current_app.logger.warning(f"Failed login attempt for user: {data.get('username')}")
    return jsonify({"message": "Invalid username or password"}), 401


@admin_routes.route("/create_user", methods=["POST"])
def route_create_user():
    try:
        logger.info("Creating user")
        create_user()
    except Exception as e:
        print("user exist")


@admin_routes.route("/load-data", methods=["POST"])
def load_data():
    try:
        logger.info("Starting data truncation")
        truncate_tables()
        logger.info("Data truncation completed")

        logger.info("Starting data loading")
        load_all_data()
        logger.info("Data loading completed successfully")

        return jsonify({"message": "Data loaded successfully"}), 200
    except Exception as e:
        logger.error(f"Error during data loading: {str(e)}")
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
