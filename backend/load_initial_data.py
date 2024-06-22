import os
from app import app
from models import db, Site

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
SITE_LIST_FILE = os.path.join(DATA_DIR, 'site_list.txt')

def parse_line(line):
    # Determine type based on prefix
    if line.startswith('--'):
        site_type = 'Extended'
        url = line[2:].strip()
    elif line.startswith('xx'):
        site_type = 'Doesn\'t work'
        url = line[2:].strip()
    else:
        site_type = 'Good'
        url = line.strip()

    # Assuming the parse method is constant or can be determined here
    parse_method = 'multi_search'  # Adjust this if parse method varies

    # Extract domain name or other identifier as name
    name = url.split('//')[-1].split('.')[0]

    return name, url, parse_method, site_type

def load_site_list():
    with open(SITE_LIST_FILE, 'r') as file:
        lines = file.readlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith('//'):
            continue  # Skip empty lines and comments

        name, url, parse_method, site_type = parse_line(line)
        
        # Check if the site already exists
        existing_site = Site.query.filter_by(name=name).first()
        if not existing_site:
            site = Site(name=name, url=url, parse_method=parse_method, type=site_type)
            db.session.add(site)

    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Ensure tables are created
        load_site_list()
