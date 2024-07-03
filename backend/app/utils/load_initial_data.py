import os
import csv
from app import create_app, db
from app.models.site import Site
from app.models.card import Card_list

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
SITE_LIST_FILE = os.path.join(DATA_DIR, 'site_list.txt')
CARD_LIST_FILE = os.path.join(DATA_DIR, 'card_list.txt')

def load_site_list():
    with open(SITE_LIST_FILE, 'r') as file:
        csv_reader = csv.reader(file)
        headers = next(csv_reader)
        print(f"Headers: {headers}")  # Debug print
        
        # Create a dictionary to map column names to indices
        column_indices = {column.strip().lower(): index for index, column in enumerate(headers)}
        
        for row in csv_reader:
            print(f"Processing row: {row}")  # Debug print
            site = Site(
                name=row[column_indices['name']].strip(),
                url=row[column_indices['url']].strip(),
                method=row[column_indices['method']].strip(),
                active=row[column_indices['active']].strip().lower() == 'yes',
                country=row[column_indices['country']].strip(),
                type=row[column_indices['type']].strip()
            )
            db.session.add(site)
    db.session.commit()

def load_card_list():
    with open(CARD_LIST_FILE, 'r') as file:
        lines = file.readlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue  # Skip empty lines
        
        quantity, card_name = line.split(' ', 1)
        quantity = int(quantity.strip())
        card_name = card_name.strip()

        card = Card_list(
            name=card_name,
            quantity=quantity,
            quality='NM',  # Default value, adjust as needed
            language='English'  # Default value
        )
        db.session.add(card)
    
    db.session.commit()

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # Drop all existing tables and recreate them
        db.drop_all()
        db.create_all()
        
        # Load data
        load_site_list()
        load_card_list()
        
        print("Data loaded successfully.")