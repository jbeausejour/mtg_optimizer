from backend.app import db
from datetime import datetime, timezone

class Scan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.now(timezone.utc))
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