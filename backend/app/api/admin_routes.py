import logging
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, jwt_required
from sqlalchemy.exc import IntegrityError
from app.services.card_manager import CardManager
from app.models.user import User
from app.utils.validators import validate_setting_key, validate_setting_value

logger = logging.getLogger(__name__)

# Admin Routes
admin_routes = Blueprint("admin_routes", __name__)

# Site Operations
@admin_routes.route("/sites", methods=["GET"])
def get_sites():
    sites = CardManager.get_all_sites()
    return jsonify([site.to_dict() for site in sites])

@admin_routes.route("/sites", methods=["POST"])
def add_site():
    try:
        data = request.json
        new_site = CardManager.add_site(data)
        return jsonify(new_site.to_dict()), 201
    except IntegrityError as ie:
        logger.error(f"Database integrity error: {str(ie)}")
        return jsonify({"error": "Database integrity error"}), 409
    except Exception as e:
        logger.error(f"Error adding site: {str(e)}")
        return jsonify({"error": "Failed to add site"}), 500

@admin_routes.route("/sites/<int:site_id>", methods=["PUT"])
def update_site(site_id):
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        updated_site = CardManager.update_site(site_id, data)
        return jsonify({
            "message": "Site updated successfully",
            "site": updated_site.to_dict(),
        }), 200
    except ValueError as ve:
        logger.warning(f"Validation error updating site: {str(ve)}")
        return jsonify({"error": str(ve)}), 400
    except IntegrityError as ie:
        logger.error(f"Integrity error updating site: {str(ie)}")
        return jsonify({"error": "Database integrity error"}), 409
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({"error": "An unexpected error occurred"}), 500

# Settings Operations
@admin_routes.route("/settings", methods=["GET"])
@jwt_required()
def get_settings():
    settings = CardManager.get_all_settings()
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

        setting = CardManager.update_setting(key, value)
        updated_settings.append(setting.to_dict())
        logger.info(f"Setting updated: {key}")

    return jsonify(updated_settings), 200

@admin_routes.route("/login", methods=["POST"])
def login():
    data = request.json
    logging.info(f"Login attempt for user: {data.get('username')}")

    user = User.query.filter_by(username=data["username"]).first()
    if user and user.check_password(data["password"]):
        access_token = create_access_token(identity=user.id)
        logging.info(f"Login successful for user: {user.username}")
        return jsonify(access_token=access_token), 200

    logging.warning(f"Failed login attempt for user: {data.get('username')}")
    return jsonify({"message": "Invalid username or password"}), 401