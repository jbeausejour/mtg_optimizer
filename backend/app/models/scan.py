from datetime import datetime, timezone
from app.extensions import db


class Scan(db.Model):
    __tablename__ = "scan"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    results = db.relationship("ScanResult", backref="scan", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.created_at.isoformat() if self.created_at else None,
            "results": [result.to_dict() for result in self.results],
        }


class ScanResult(db.Model):
    __tablename__ = "scan_result"
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey("scan.id", name="fk_ScanResult_scan_id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)  # Changed from card_name
    site_id = db.Column(db.Integer, db.ForeignKey("site.id", name="fk_ScanResult_site_id"), nullable=False)
    price = db.Column(db.Float, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    edition = db.Column(db.String(255))  # Added new columns
    version = db.Column(db.String(255))
    foil = db.Column(db.Boolean)
    quality = db.Column(db.String(50))
    language = db.Column(db.String(50))
    quantity = db.Column(db.Integer)

    site = db.relationship("Site", back_populates="scan_results")

    def __repr__(self):
        return f"<ScanResult {self.id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'edition': self.edition,
            'version': self.version,
            'foil': self.foil,
            'quality': self.quality,
            'language': self.language,
            'quantity': self.quantity,
            'price': self.price,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
