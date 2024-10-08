from app.extensions import db
from datetime import datetime, timezone

class MarketplaceCard(db.Model):
    __tablename__ = 'marketplace_card'
    id = db.Column(db.Integer, primary_key=True)
    site = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    edition = db.Column(db.String(255), nullable=False)
    version = db.Column(db.String(255))
    foil = db.Column(db.Boolean, nullable=False, default=False)
    quality = db.Column(db.String(255), nullable=False)
    language = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    set_id = db.Column(db.String(36), db.ForeignKey('sets.id', name='fk_card_set_id'))
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    set = db.relationship('Sets', back_populates='marketplace_cards')
    scan_results = db.relationship('ScanResult', back_populates='marketplace_card')

    def to_dict(self):
        return {
            'id': self.id,
            'site': self.site,
            'name': self.name,
            'edition': self.edition,
            'version': self.version,
            'foil': self.foil,
            'quality': self.quality,
            'language': self.language,
            'quantity': self.quantity,
            'price': self.price,
            'set_id': self.set_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<MarketplaceCard {self.name}>'

class UserBuylistCard(db.Model):
    __tablename__ = 'user_buylist_card'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    edition = db.Column(db.String(255))
    version = db.Column(db.String(255))
    foil = db.Column(db.Boolean, default=False)
    quality = db.Column(db.String(255), nullable=False)
    language = db.Column(db.String(255), nullable=False, default="English")
    quantity = db.Column(db.Integer, nullable=False, default=1)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'edition': self.edition,
            'version': self.version,
            'foil': self.foil,
            'quality': self.quality,
            'language': self.language,
            'quantity': self.quantity
        }

class ScryfallCardData(db.Model):
    __tablename__ = 'scryfall_card_data'
    id = db.Column(db.Integer, primary_key=True)
    card_name = db.Column(db.String(255), nullable=False)
    oracle_id = db.Column(db.String(255), nullable=False)
    multiverse_ids = db.Column(db.String(255))
    reserved = db.Column(db.Boolean)
    lang = db.Column(db.String(10))
    set_code = db.Column(db.String(10))
    set_name = db.Column(db.String(255))
    collector_number = db.Column(db.String(20))
    variation = db.Column(db.Boolean)
    promo = db.Column(db.Boolean)
    prices = db.Column(db.JSON)
    purchase_uris = db.Column(db.JSON)
    cardconduit_data = db.Column(db.JSON)
    scan_timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    purchase_data = db.Column(db.JSON)

    def __repr__(self):
        return f'<CardData {self.card_name}>'
