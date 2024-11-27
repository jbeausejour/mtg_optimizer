from datetime import datetime, timezone
from app.extensions import db
from .base_card import BaseCard


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


class ScanResult(BaseCard):
    __tablename__ = "scan_result"
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey("scan.id"))
    site_id = db.Column(db.Integer, db.ForeignKey("site.id"))
    price = db.Column(db.Float, nullable=False)
    quality = db.Column(db.String(50))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    site = db.relationship("Site", back_populates="scan_results")

    def __repr__(self):
        return f"<ScanResult {self.id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'set_name': self.set_name,  # Changed from 'edition'
            'version': self.version,
            'foil': self.foil,
            'quality': self.quality,
            'language': self.language,
            'quantity': self.quantity,
            'price': self.price,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def validate_data(cls, data):
        """Ensure data meets schema requirements"""
        # Standardize name key if it exists in different formats
        name_keys = ['name', 'Name', 'card_name', 'cardName']
        for key in name_keys:
            if key in data and key != 'name':
                data['name'] = data.pop(key)
                break
                
        if not data.get('name'):
            raise ValueError("Name is required")
        
        if not data.get('site_id'):
            raise ValueError("Site ID is required")
            
        if not data.get('scan_id'):
            raise ValueError("Scan ID is required")
            
        if data.get('price') is None:
            raise ValueError("Price is required")
            
        # Set defaults
        data.setdefault('language', 'English')
        data.setdefault('version', 'Standard')
        data.setdefault('foil', False)
        data.setdefault('quantity', 0)
        
        return data

    def __init__(self, **kwargs):
        kwargs = self.validate_data(kwargs)
        super().__init__(**kwargs)
