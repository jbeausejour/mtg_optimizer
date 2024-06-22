from models import db, Site

def get_all_sites():
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

    site.name = data.get('name', site.name)
    site.url = data.get('url', site.url)
    site.parse_method = data.get('parse_method', site.parse_method)
    site.type = data.get('type', site.type)
    db.session.commit()

    return {'message': 'Site updated successfully'}

def delete_site(site_id):
    site = Site.query.get(site_id)
    if not site:
        return {'error': 'Site not found'}, 404

    db.session.delete(site)
    db.session.commit()
    return {'message': 'Site deleted successfully'}
