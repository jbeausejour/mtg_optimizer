import logging

from app.models.user import User
from app.services.admin_service import AdminService
from app.utils.load_initial_data import load_all_data, truncate_tables
from app.utils.validators import validate_setting_key, validate_setting_value
from quart import Blueprint, request, jsonify
from quart_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    verify_jwt_in_request,
    get_jwt_claims,
)
from sqlalchemy.future import select
from app.utils.async_context_manager import flask_session_scope

logger = logging.getLogger(__name__)

# Admin Routes
admin_routes = Blueprint("admin_routes", __name__)


# Settings Operations
# Settings Operations
@admin_routes.route("/settings", methods=["GET"])
@jwt_required
async def get_settings():
    logger.info("Getting all settings")
    async with flask_session_scope() as session:
        settings = await AdminService.get_all_settings(session)

        # Convert settings to a dictionary format for frontend consumption
        settings_dict = {}
        for setting in settings:
            key = setting.key
            value = setting.value

            # Convert stored string values back to appropriate types
            if key in ["itemsPerPage", "priceAlertThreshold"]:
                try:
                    settings_dict[key] = int(value) if value else 0
                except (ValueError, TypeError):
                    settings_dict[key] = 0
            elif key == "enablePriceAlerts":
                # Convert string boolean back to actual boolean
                settings_dict[key] = value.lower() in ["true", "1", "yes", "on"] if value else False
            else:
                settings_dict[key] = value

        return jsonify(settings_dict)


def normalize_setting_value(key: str, value):
    """Normalize setting values to appropriate types and convert to string for storage"""
    if value is None:
        return ""

    # Handle boolean fields
    if key == "enablePriceAlerts":
        if isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, str):
            return value.lower() if value.lower() in ["true", "false"] else "false"
        else:
            return "false"

    # Handle numeric fields
    elif key in ["itemsPerPage", "priceAlertThreshold"]:
        try:
            # Convert to number first to validate, then back to string for storage
            if isinstance(value, str) and value.strip() == "":
                return "0"
            num_value = float(value)
            if key == "itemsPerPage":
                num_value = int(num_value)  # itemsPerPage should be integer
            return str(num_value)
        except (ValueError, TypeError):
            return "0"

    # Handle string fields
    else:
        return str(value) if value is not None else ""


@admin_routes.route("/settings", methods=["POST"])
@jwt_required
async def update_settings():
    try:
        data = await request.get_json()
        if not data or not isinstance(data, dict):
            return jsonify({"error": "Invalid data"}), 400

        async with flask_session_scope() as session:
            updated_settings = []

            for key, value in data.items():
                # Normalize the value for storage and validation
                normalized_value = normalize_setting_value(key, value)

                # Validate the key and normalized value
                if not validate_setting_key(key):
                    logger.error(f"Invalid setting key: {key}")
                    return jsonify({"error": f"Invalid setting key: {key}"}), 400

                if not validate_setting_value(normalized_value):
                    logger.error(f"Invalid setting value for key '{key}': {normalized_value}")
                    return jsonify({"error": f"Invalid setting value for key: {key}"}), 400

                # Update the setting
                setting = await AdminService.update_setting(session, key, normalized_value)
                updated_settings.append(setting.to_dict())
                logger.info(f"Setting updated: {key} = {normalized_value}")

            await session.commit()
            return jsonify(updated_settings), 200

    except Exception as e:
        logger.error(f"Error updating settings: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@admin_routes.route("/login", methods=["POST"])
async def login():
    data = await request.get_json()

    # Try Authelia-authenticated session first
    forwarded_user = request.headers.get("Remote-User")
    logger.info(f"[login attempt] for: {forwarded_user}")
    if forwarded_user:
        async with flask_session_scope() as session:
            stmt = select(User).where(User.username == forwarded_user)
            result = await session.execute(stmt)
            user = result.scalars().first()

            if user:
                logger.info(f"[login] Authelia session login for: {forwarded_user}")
                access_token = create_access_token(identity=user.id)
                refresh_token = create_refresh_token(identity=user.id)
                return jsonify(access_token=access_token, refresh_token=refresh_token), 200

    # Fallback to password-based login
    if not data or "username" not in data or "password" not in data:
        return jsonify({"error": "Missing credentials"}), 400

    username = data["username"]
    password = data["password"]

    async with flask_session_scope() as session:
        stmt = select(User).where(User.username == username)
        result = await session.execute(stmt)
        user = result.scalars().first()

        if not user or not user.check_password(password):
            return jsonify({"error": "Invalid credentials"}), 401

        logger.info(f"[login] Manual login for: {username}")
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        return jsonify(access_token=access_token, refresh_token=refresh_token), 200


@admin_routes.route("/refresh-token", methods=["POST"])
@jwt_required
async def refresh_token():
    try:
        # 1. First try JWT refresh token
        await verify_jwt_in_request()
        claims = get_jwt_claims()
        if claims.get("type") != "refresh":
            return jsonify({"error": "Only refresh tokens allowed"}), 401

        identity = get_jwt_identity()

    except Exception:
        # 2. Fallback to Authelia session
        username = request.headers.get("Remote-User")
        if not username:
            return jsonify({"error": "Unauthorized"}), 401

        async with flask_session_scope() as session:
            stmt = select(User).where(User.username == username)
            result = await session.execute(stmt)
            user = result.scalars().first()

            if not user:
                return jsonify({"error": "Authelia user not found"}), 401

            identity = user.id

    # 3. Issue new tokens
    access_token = create_access_token(identity=identity)
    refresh_token = create_refresh_token(identity=identity)
    return jsonify(access_token=access_token, refresh_token=refresh_token)


@admin_routes.route("/create_user", methods=["POST"])
async def route_create_user():

    try:
        logger.info("Received request to create user")

        data = await request.get_json()
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")

        if not username or not email or not password:
            return jsonify({"error": "Missing username, email, or password"}), 400

        async with flask_session_scope() as session:
            user = await AdminService.create_user(session, username, email, password)

        return jsonify({"message": f"User {user.username} created successfully."}), 201

    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return jsonify({"error": str(e)}), 500


@admin_routes.route("/load-data", methods=["POST"])
async def load_data():
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
