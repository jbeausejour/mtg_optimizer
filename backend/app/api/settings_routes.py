
from flask import Blueprint, jsonify, request
from app.services.settings_service import SettingsService
from app.models.user import User
from flask_jwt_extended import create_access_token
from flask_jwt_extended import jwt_required
from app.utils.validators import validate_setting_key, validate_setting_value
import logging


logger = logging.getLogger(__name__)

settings_routes = Blueprint('settings_routes', __name__)

@settings_routes.route('/settings', methods=['GET'])
@jwt_required()
def get_settings():
    settings = SettingsService.get_all_settings()
    return jsonify([setting.to_dict() for setting in settings])

@settings_routes.route('/settings', methods=['POST'])
@jwt_required()
def update_settings():
    data = request.json
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'Invalid data'}), 400

    updated_settings = []
    for key, value in data.items():
        if not validate_setting_key(key) or not validate_setting_value(value):
            return jsonify({'error': f'Invalid setting key or value: {key}'}), 400
        
        setting = SettingsService.update_setting(key, value)
        updated_settings.append(setting.to_dict())
        logger.info(f"Setting updated: {key}")

    return jsonify(updated_settings), 200

@settings_routes.route('/settings/<key>', methods=['GET'])
@jwt_required()
def get_setting(key):
    if not validate_setting_key(key):
        return jsonify({'error': 'Invalid setting key'}), 400
    
    setting = SettingsService.get_setting(key)
    if setting:
        return jsonify(setting.to_dict())
    return jsonify({'error': 'Setting not found'}), 404

@settings_routes.route('/settings/<key>', methods=['DELETE'])
@jwt_required()
def delete_setting(key):
    if not validate_setting_key(key):
        return jsonify({'error': 'Invalid setting key'}), 400
    
    if SettingsService.delete_setting(key):
        logger.info(f"Setting deleted: {key}")
        return jsonify({'message': 'Setting deleted successfully'}), 200
    return jsonify({'error': 'Setting not found'}), 404

@settings_routes.route('/login', methods=['POST'])
def login():
    data = request.json
    logging.info(f"Login attempt for user: {data.get('username')}")
    
    user = User.query.filter_by(username=data['username']).first()
    if user and user.check_password(data['password']):
        access_token = create_access_token(identity=user.id)
        logging.info(f"Login successful for user: {user.username}")
        return jsonify(access_token=access_token), 200
    
    logging.warning(f"Failed login attempt for user: {data.get('username')}")
    return jsonify({'message': 'Invalid username or password'}), 401