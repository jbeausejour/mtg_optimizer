import logging

from app.models.user import User
from app.services.admin_service import AdminService
from app.utils.load_initial_data import load_all_data, truncate_tables
from app.utils.validators import validate_setting_key, validate_setting_value
from quart import Blueprint, request, jsonify
from quart_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from sqlalchemy.future import select
from app.utils.async_context_manager import flask_session_scope

logger = logging.getLogger(__name__)

# Admin Routes
admin_routes = Blueprint("admin_routes", __name__)


# Settings Operations
@admin_routes.route("/settings", methods=["GET"])
@jwt_required
async def get_settings():
    logger.info("Getting all settings")
    settings = AdminService.get_all_settings()
    return jsonify([setting.to_dict() for setting in settings])


@admin_routes.route("/settings", methods=["POST"])
@jwt_required
async def update_settings():
    data = await request.get_json()
    if not data or not isinstance(data, dict):
        return jsonify({"error": "Invalid data"}), 400

    updated_settings = []
    for key, value in data.items():
        if not validate_setting_key(key) or not validate_setting_value(value):
            return jsonify({"error": f"Invalid setting key or value: {key}"}), 400

        setting = AdminService.update_setting(key, value)
        updated_settings.append(setting.to_dict())
        logger.info(f"Setting updated: {key}")

    return jsonify(updated_settings), 200


@admin_routes.route("/login", methods=["POST"])
async def login():
    data = await request.get_json()
    forwarded_user = request.headers.get("X-Forwarded-User")

    async with flask_session_scope() as session:
        if forwarded_user:
            logger.info(f"Login via Authelia for user: {forwarded_user}")
            stmt = select(User).where(User.username == forwarded_user)
            result = await session.execute(stmt)
            user = result.scalars().first()

            if not user:
                return jsonify({"msg": "User not found"}), 404

            # No password needed with Authelia
            access_token = create_access_token(identity=user.id)
            logger.info(f"Authelia login successful for user: {user.username}")
            return jsonify(access_token=access_token, userId=user.id), 200

        # Manual login
        logger.info(f"Login attempt for user: {data.get('username')}")
        stmt = select(User).where(User.username == data["username"])
        result = await session.execute(stmt)
        user = result.scalars().first()

        if user and user.check_password(data["password"]):
            access_token = create_access_token(identity=user.id)
            logger.info(f"Login successful for user: {user.username}")
            return jsonify(access_token=access_token, userId=user.id), 200

        logger.warning(f"Failed login attempt for user: {data.get('username')}")
        return jsonify({"message": "Invalid username or password"}), 401


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
