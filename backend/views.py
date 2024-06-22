from flask import Blueprint, jsonify, request
from models import db, Site, Card
from services import get_all_sites, add_site, delete_site, update_site
from mtg_utils import fetch_all_card_details
import pandas as pd

views = Blueprint('views', __name__)

@views.route('/get_site_list', methods=['GET'])
def get_site_list():
    sites = get_all_sites()
    return jsonify([site.to_dict() for site in sites])

@views.route('/add_site', methods=['POST'])
def add_site_route():
    data = request.json
    site = add_site(data)
    return jsonify(site.to_dict())

@views.route('/delete_site/<int:site_id>', methods=['DELETE'])
def delete_site_route(site_id):
    delete_site(site_id)
    return jsonify({'message': 'Site deleted successfully'})

@views.route('/update_site/<int:site_id>', methods=['PUT'])
def update_site_route(site_id):
    data = request.json
    site = update_site(site_id, data)
    return jsonify(site.to_dict())

@views.route('/search_cards', methods=['POST'])
def search_cards():
    data = request.json
    card_list = data['card_list']
    special_site_flag = data['special_site_flag']
    sites_results_df = fetch_all_card_details(card_list, special_site_flag)
    if sites_results_df is not None and not sites_results_df.empty:
        return jsonify(sites_results_df.to_dict(orient='records'))
    else:
        return jsonify([])
