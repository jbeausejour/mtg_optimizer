from flask import Blueprint, jsonify, request
from models import db, Site, CardScan
from services import get_all_sites, add_site, update_site, delete_site
import requests
from flask_cors import CORS
from htmldom import htmldom
from fuzzywuzzy import process
from html import unescape
import urllib

views = Blueprint('views', __name__)

SCRYFALL_API_URL = "https://api.scryfall.com/cards/named"
MTGSTOCKS_BASE_URL = 'http://www.mtgstocks.com'
QUERY_STRING = '/cards/search?utf8=%E2%9C%93&print%5Bcard%5D={}&button='
SETS_PATH = MTGSTOCKS_BASE_URL + '/sets'

def generate_search_url(name):
    formatted_name = urllib.parse.quote('+'.join(name.split(' ')), '/+')
    return MTGSTOCKS_BASE_URL + QUERY_STRING.format(formatted_name)

def get_matching_item_on_page(url, text, selector):
    page = htmldom.HtmlDom(url)
    page.createDom()
    elems = page.find(selector)
    possible_matches = [elem.text() for elem in elems]
    best_match = process.extractOne(text, possible_matches)
    match_index = possible_matches.index(best_match[0])
    return elems[match_index]

def get_card_url_from_search_results(search_url, name):
    card_link = get_matching_item_on_page(search_url, name, '.table > tbody > tr > td > a')
    return MTGSTOCKS_BASE_URL + card_link.attr('href')

def card_url_from_name(name):
    query_url = generate_search_url(name)
    response = requests.get(query_url, allow_redirects=False)
    if response.status_code in range(301, 307):
        return response.headers['Location']
    elif response.status_code == requests.codes.ok:
        return get_card_url_from_search_results(query_url, name)
    return None

def scrape_price(card_url):
    card_page = htmldom.HtmlDom(card_url)
    card_page.createDom()
    card_name = card_page.find('h2 > a').text()
    card_set = card_page.find('h5 > a').text()
    price_values = [elem.text() for elem in card_page.find('.priceheader')]
    price_keys = ['avg']
    if len(price_values) > 1:
        price_keys.insert(0, 'low')
        price_keys.append('high')
    return {
        'name': unescape(card_name),
        'set': unescape(card_set),
        'link': card_url,
        'promo': len(price_keys) == 1,
        'prices': dict(zip(price_keys, price_values))
    }

def get_card_price(name):
    card_url = card_url_from_name(name)
    return scrape_price(card_url) if card_url else {'error': 'Card not found'}


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

@views.route('/fetch_card', methods=['GET'])
def fetch_card():
    """
    Fetch card data from Scryfall API and MTGStocks, along with previous scan info from the database.
    """
    card_name = request.args.get('name')
    
    # Fetch data from Scryfall API
    scryfall_response = requests.get(SCRYFALL_API_URL, params={'fuzzy': card_name})
    if scryfall_response.status_code != 200:
        return jsonify({'error': 'Failed to fetch data from Scryfall API'}), scryfall_response.status_code
    scryfall_data = scryfall_response.json()
    
    # Fetch data from MTGStocks
    mtgstocks_data = get_card_price(card_name)
    
    # Fetch previous scan info from the database
    previous_scan = db.session.query(CardScan).filter_by(name=card_name).first()
    previous_scan_data = previous_scan.to_dict() if previous_scan else None
    
    card_data = {
        'scryfall': scryfall_data,
        'mtgstocks': mtgstocks_data,
        'previous_scan': previous_scan_data
    }

    return jsonify(card_data)

