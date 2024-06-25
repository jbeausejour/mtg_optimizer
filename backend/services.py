from models import db, Site

def get_all_sites():
    """Retrieve all sites from the database."""
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
    
    print(f"Updating site {site_id} with data: {data}")  # Debugging log

    changes_made = False
    
    if site.name != data.get('name', site.name):
        site.name = data.get('name', site.name)
        changes_made = True
    if site.url != data.get('url', site.url):
        site.url = data.get('url', site.url)
        changes_made = True
    if site.parse_method != data.get('parse_method', site.parse_method):
        site.parse_method = data.get('parse_method', site.parse_method)
        changes_made = True
    if site.type != data.get('type', site.type):
        site.type = data.get('type', site.type)
        changes_made = True

    if not changes_made:
        print(f"No changes detected for site {site_id}.")  # Add logging here
        return {'message': 'No changes detected, no update necessary'}, 200

    try:
        db.session.commit()
        print(f"Site {site_id} updated successfully.")  # Add logging here
        return {'message': 'Site updated successfully'}, 200
    except Exception as e:
        db.session.rollback()
        print(f"Error updating site {site_id}: {e}")  # Add logging here
        return {'error': str(e)}, 500
    
def delete_site(site_id):
    site = Site.query.get(site_id)
    if not site:
        return {'error': 'Site not found'}, 404

    db.session.delete(site)
    db.session.commit()
    return {'message': 'Site deleted successfully'}
