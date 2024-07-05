from app import db
from datetime import datetime, timezone

class Sets(db.Model):
    __tablename__ = 'sets'

    id = db.Column(db.Integer, primary_key=True)
    set_code = db.Column(db.String(10), unique=True, nullable=False)
    set_name = db.Column(db.String(255), nullable=False)
    set_type = db.Column(db.String(50), nullable=False)
    released_at = db.Column(db.Date)
    last_updated = db.Column(db.DateTime, default=datetime.now(timezone.utc()))

    def to_dict(self):
        return {
            'set_code': self.set_code,
            'set_name': self.set_name,
            'set_type': self.set_type,
            'released_at': self.released_at.isoformat() if self.released_at else None
        }