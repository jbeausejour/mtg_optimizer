from app import db
from datetime import datetime, timedelta, timezone

class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    url = db.Column(db.String(255), unique=True, nullable=False)
    method = db.Column(db.String(50), nullable=False)
    active = db.Column(db.Boolean, nullable=False)
    country = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(50), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'method': self.method,
            'active': self.active,
            'country': self.country,
            'type': self.type
        }

class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    edition = db.Column(db.String(255), nullable=False)
    version = db.Column(db.String(255), nullable=True)
    foil = db.Column(db.Boolean, nullable=False, default=False)
    quality = db.Column(db.String(255), nullable=False)
    language = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

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
            'price': self.price
        }

class Card_list(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    edition = db.Column(db.String(255), nullable=True)
    version = db.Column(db.String(255), nullable=True)
    foil = db.Column(db.Boolean, nullable=True, default=False)
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
    
class OptimizationResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    card_names = db.Column(db.JSON)
    results = db.Column(db.JSON)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'card_names': self.card_names,
            'results': self.results,
            'timestamp': self.timestamp.isoformat()
        }

class Scan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    results = db.relationship('ScanResult', backref='scan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'results': [result.to_dict() for result in self.results]
        }
 
class ScanResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scan.id'), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey('card.id'), nullable=False)
    site = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)

    card = db.relationship('Card', backref='scan_results')

    def to_dict(self):
        return {
            'id': self.id,
            'card_name': self.card.name,
            'quantity': self.card.quantity,
            'site': self.site,
            'price': self.price
        }
