from flask import Blueprint, jsonify, request
from models import db, Site
from services import get_all_sites, add_site, update_site, delete_site

views = Blueprint('views', __name__)

@views.route('/get_site_list', methods=['GET'])
def get_site_list():
    sites = get_all_sites()
    return jsonify([site.to_dict() for site in sites])

@views.route('/add_site', methods=['POST'])
def add_site_route():
    data = request.json
    result, status = add_site(data)
    return jsonify(result), status

@views.route('/update_site/<int:site_id>', methods=['PUT'])
def update_site_route(site_id):
    data = request.json
    result, status = update_site(site_id, data)
    return jsonify(result), status

@views.route('/delete_site/<int:site_id>', methods=['DELETE'])
def delete_site_route(site_id):
    result, status = delete_site(site_id)
    return jsonify(result), status
