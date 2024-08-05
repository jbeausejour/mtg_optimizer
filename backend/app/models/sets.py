from app import db
from datetime import datetime, timezone

class Sets(db.Model):
    __tablename__ = 'sets'

    id = db.Column(db.Integer, primary_key=True)
    set_name = db.Column(db.String(255), nullable=False)
    set_code = db.Column(db.String(10), unique=True, nullable=False)
    set_symbol = db.Column(db.String(50))
    set_type = db.Column(db.String(50), nullable=False)
    release_date = db.Column(db.Date)
    card_count = db.Column(db.Integer)
    is_digital = db.Column(db.Boolean, default=False)
    last_updated = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    cards = db.relationship('Card', back_populates='sets')
    

    def to_dict(self):
        return {
            'id': self.id,
            'set_name': self.set_name,
            'set_code': self.set_code,
            'set_symbol': self.set_symbol,
            'set_type': self.set_type,
            'release_date': self.release_date,
            'card_count': self.card_count,
            'is_digital': self.is_digital,
            'last_updated': self.last_updated.isoformat() if self.release_date else None
        }
