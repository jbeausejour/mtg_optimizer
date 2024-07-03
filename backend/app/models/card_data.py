from app import db
from datetime import datetime

class CardData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    card_name = db.Column(db.String(255), nullable=False)
    oracle_id = db.Column(db.String(255), nullable=False)
    multiverse_ids = db.Column(db.String(255))  # Store as comma-separated string
    reserved = db.Column(db.Boolean)
    lang = db.Column(db.String(10))
    set_code = db.Column(db.String(10))
    set_name = db.Column(db.String(255))
    collector_number = db.Column(db.String(20))
    variation = db.Column(db.Boolean)
    promo = db.Column(db.Boolean)
    prices = db.Column(db.JSON)  # Store Scryfall prices as JSON
    purchase_uris = db.Column(db.JSON)  # Store purchase URIs as JSON
    cardconduit_data = db.Column(db.JSON)  # Store CardConduit data as JSON
    scan_timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CardData {self.card_name}>'