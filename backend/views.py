from flask import Blueprint, request, jsonify
from services import get_all_sites, add_site, update_site, delete_site

# Example card list stored in a file or database
CARD_LIST_FILE = 'data/card_list.txt'

app = Blueprint('views', __name__)

@app.route('/get_site_list', methods=['GET'])
def get_site_list():
    sites = get_all_sites()
    site_list = [{
        'id': site.id,
        'name': site.name,
        'url': site.url,
        'parse_method': site.parse_method,
        'type': site.type
    } for site in sites]
    return jsonify(site_list)

@app.route('/add_site', methods=['POST'])
def add_site_route():
    data = request.get_json()
    response, status = add_site(data)
    return jsonify(response), status

@app.route('/update_site/<int:site_id>', methods=['PUT'])
def update_site_route(site_id):
    data = request.get_json()
    response = update_site(site_id, data)
    return jsonify(response)

@app.route('/delete_site/<int:site_id>', methods=['DELETE'])
def delete_site_route(site_id):
    response = delete_site(site_id)
    return jsonify(response)

@app.route('/get_card_list', methods=['GET'])
def get_card_list():
    try:
        with open(CARD_LIST_FILE, 'r') as file:
            card_list = file.read()
        return card_list, 200
    except Exception as e:
        return str(e), 500
