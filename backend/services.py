from models import db, Site, Card, Card_list
import logging

logger = logging.getLogger(__name__)


def get_all_sites():
    #logger.debug("get_all_sites")
    #print("get_all_sites")
    return Site.query.all()

def get_site_by_id(site_id):
    return Site.query.get(site_id)

def add_site(data):
    name = data.get('name')
    url = data.get('url')
    parse_method = data.get('parse_method')
    type = data.get('type')

    existing_site = Site.query.filter_by(name=name).first()
    if existing_site:
        return {'error': 'Site already exists'}, 400

    new_site = Site(name=name, url=url, parse_method=parse_method, type=type)
    db.session.add(new_site)
    db.session.commit()
    return {'message': 'Site added successfully'}, 201

def update_site(site_id, data):
    site = Site.query.get(site_id)
    if not site:
        return {'error': 'Site not found'}, 404

    if site.name != data.get('name', site.name):
        site.name = data.get('name', site.name)
    if site.url != data.get('url', site.url):
        site.url = data.get('url', site.url)
    if site.parse_method != data.get('parse_method', site.parse_method):
        site.parse_method = data.get('parse_method', site.parse_method)
    if site.type != data.get('type', site.type):
        site.type = data.get('type', site.type)

    db.session.commit()
    return {'message': 'Site updated successfully'}, 200

def delete_site(site_id):
    site = Site.query.get(site_id)
    if not site:
        return {'error': 'Site not found'}, 404

    db.session.delete(site)
    db.session.commit()
    return {'message': 'Site deleted successfully'}

def get_all_cards():
    #logger.debug("LOG: /cards in Services")
    #print("/cards in services")
    #print(db.engine)
    #print(Card_list.query.all())
    return Card_list.query.all()

def get_card_by_id(card_id):
    return Card_list.query.get(card_id)
 