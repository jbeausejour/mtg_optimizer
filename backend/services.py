import requests
from models import Card, Card_list, Site, Scan, ScanResult
from htmldom import htmldom
from html import unescape
import urllib
from fuzzywuzzy import process

SCRYFALL_API_URL = "https://api.scryfall.com/cards/named"
SCRYFALL_SEARCH_API_URL = "https://api.scryfall.com/cards/search"
MTGSTOCKS_BASE_URL = 'http://www.mtgstocks.com'
QUERY_STRING = '/cards/search?utf8=%E2%9C%93&print%5Bcard%5D={}&button='

def get_all_cards():
    print('Getting cards !')
    return Card_list.query.all()

def get_all_sites():
    print('Getting sites !')
    return Site.query.all()

def get_card_versions(card_name):
    response = requests.get(SCRYFALL_SEARCH_API_URL, params={'q': f'!"{card_name}"'})
    response.raise_for_status()
    
    data = response.json()
    sets = set()
    languages = set()
    versions = set()

    for card in data['data']:
        sets.add((card['set'], card['set_name']))
        languages.add(card['lang'])
        if 'finishes' in card:
            versions.update(card['finishes'])

    return {
        'name': card_name,
        'sets': [{'code': code, 'name': name} for code, name in sets],
        'languages': list(languages),
        'versions': list(versions)
    }

def fetch_card_data(card_name, set_code=None, language=None, version=None):
    scryfall_data = fetch_scryfall_data(card_name, set_code, language)
    mtgstocks_data = fetch_mtgstocks_data(card_name, set_code)

    # Add version information to Scryfall data
    scryfall_data['version'] = version

    return {
        'scryfall': scryfall_data,
        'mtgstocks': mtgstocks_data,
    }

def fetch_scryfall_data(card_name, set_code=None, language=None):
    params = {'fuzzy': card_name}
    if set_code:
        params['set'] = set_code
    if language:
        params['lang'] = language

    response = requests.get(SCRYFALL_API_URL, params=params)
    response.raise_for_status()
    return response.json()

def fetch_mtgstocks_data(card_name, set_code=None):
    search_name = f"{card_name} ({set_code})" if set_code else card_name
    card_url = card_url_from_name(search_name)
    return scrape_price(card_url) if card_url else {'error': 'Card not found'}

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

def get_scan_results(scan_id):
    scan = Scan.query.get_or_404(scan_id)
    return scan

def get_all_scan_results():
    scans = Scan.query.order_by(Scan.date.desc()).limit(5).all()
    return scans
