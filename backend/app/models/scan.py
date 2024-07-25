from app import db
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
    scan_id = db.Column(db.Integer, db.ForeignKey('scan.id', name='fk_ScanResult_scan_id'), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey('card.id', name='fk_ScanResult_card_id'), nullable=False)
    site_id = db.Column(db.Integer, db.ForeignKey('site.id', name='fk_ScanResult_site_id'), nullable=False)
    price = db.Column(db.Float, nullable=False)

    site = db.relationship('Site', back_populates='scan_results')

    def __repr__(self):
        return f'<ScanResult {self.id}>'
    
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