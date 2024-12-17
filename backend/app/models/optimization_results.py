from datetime import datetime
from app.extensions import db

class OptimizationResult(db.Model):
    __tablename__ = 'optimization_results'

    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scan.id'), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(255))
    sites_scraped = db.Column(db.Integer)
    cards_scraped = db.Column(db.Integer)
    solutions = db.Column(db.JSON)
    errors = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    scan = db.relationship(
        'Scan',
        back_populates='optimization_result',
        overlaps="optimization_results"
    )

    def to_dict(self):
        """Basic dictionary representation of the model"""
        return {
            'id': self.id,
            'scan_id': self.scan_id,
            'status': self.status,
            'message': self.message,
            'sites_scraped': self.sites_scraped,
            'cards_scraped': self.cards_scraped,
            'solutions': self.solutions,
            'errors': self.errors,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }