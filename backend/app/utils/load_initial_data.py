import os
import csv
from flask import current_app
from app.extensions import db
from app.models.site import Site
from app.models.card import UserBuylistCard
from sqlalchemy import text, inspect

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, '..', '..', 'data')

SITE_LIST_FILE = os.path.join(DATA_DIR, 'site_list.txt')
CARD_LIST_FILE = os.path.join(DATA_DIR, 'card_list.txt')
SQL_FILE = os.path.join(DATA_DIR, 'sql', 'magic_sets.sql')


def truncate_tables():
    # Delete all rows from each table
    # db.session.query(Site).delete()
    db.session.query(UserBuylistCard).delete()
    # db.session.query(Sets).delete()
    
    # Check if sqlite_sequence table exists
    inspector = inspect(db.engine)
    if 'sqlite_sequence' in inspector.get_table_names():
        # Reset the autoincrement counters
        db.session.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('site', 'card_list', 'sets')"))
    
    # Commit the changes
    db.session.commit()

def load_site_list():
    with open(SITE_LIST_FILE, 'r') as file:
        csv_reader = csv.reader(file)
        headers = next(csv_reader)
        print(f"Headers: {headers}")  # Debug print
        
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
            db.session.merge(site)  # Use merge to add or update
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

        card = UserBuylistCard(
            name=card_name,
            quantity=quantity,
            quality='NM',  # Default value, adjust as needed
            language='English'  # Default value
        )
        db.session.merge(card)  # Use merge to add or update
    
    db.session.commit()

def load_sql_file():
    with open(SQL_FILE, 'r') as file:
        sql_commands = file.read()
    
    # Split the SQL commands
    commands = sql_commands.split(';')
    
    with db.engine.connect() as connection:
        for command in commands:
            command = command.strip()
            if command:
                # Modify the CREATE TABLE command for SQLite
                if command.upper().startswith('CREATE TABLE'):
                    command = command.replace('INT AUTO_INCREMENT', 'INTEGER AUTOINCREMENT')
                    command = command.replace('BOOLEAN', 'INTEGER')  # SQLite uses INTEGER for boolean
                
                try:
                    connection.execute(text(command))
                    connection.commit()
                except Exception as e:
                    print(f"Error executing command: {command}\n{e}")

def load_all_data():
    # load_site_list()
    load_card_list()
    # load_sql_file()

if __name__ == '__main__':
    with current_app.app_context():
        # Truncate specified tables
        truncate_tables()
        
        # Load data
        load_all_data()
        
        print("Data loaded successfully.")