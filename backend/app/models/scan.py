from datetime import datetime, timezone
from app.extensions import db
from .base_card import BaseCard
from sqlalchemy.orm import relationship, validates

class Scan(db.Model):
    __tablename__ = "scan"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    # Define one-to-many relationship
    scan_results = relationship("ScanResult", backref="scan", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "date": self.created_at.isoformat() if self.created_at else None,
            "results": [result.to_dict() for result in self.scan_results],
        }

class ScanResult(BaseCard):
    __tablename__ = "scan_result"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scan.id'), nullable=False)
    site_id = db.Column(db.Integer, db.ForeignKey('site.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Remove duplicate relationship definition
    site = relationship('Site', backref='scan_results')

    def __init__(self, **kwargs):
        """Initialize with validation"""
        super().__init__(**kwargs)
        self.validate_data()

    def __repr__(self):
        """Representation for debugging and logging"""
        return f'<ScanResult {self.name} from site {self.site_id} at {self.price}>'

    def to_dict(self):
        """
        Convert to dictionary for API responses and DTO conversion
        Includes both BaseCard fields and ScanResult specific fields
        """
        base_dict = super().to_dict() if hasattr(super(), 'to_dict') else {}
        scan_dict = {
            'id': self.id,
            'scan_id': self.scan_id,
            'site_id': self.site_id,
            'price': float(self.price) if self.price else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'site_name': self.site.name if self.site else None
        }
        return {**base_dict, **scan_dict}

    @validates('price')
    def validate_price(self, key, price):
        """Ensure price is non-negative"""
        if price is not None and float(price) < 0:
            raise ValueError("Price cannot be negative")
        return price

    @validates('scan_id')
    def validate_scan_id(self, key, scan_id):
        """Ensure scan_id is provided"""
        if not scan_id:
            raise ValueError("Scan ID is required")
        return scan_id

    @validates('site_id')
    def validate_site_id(self, key, site_id):
        """Ensure site_id is provided"""
        if not site_id:
            raise ValueError("Site ID is required")
        return site_id

    @validates('updated_at')
    def validate_updated_at(self, key, updated_at):
        """Ensure updated_at is a valid datetime"""
        if updated_at and not isinstance(updated_at, datetime):
            raise ValueError("Updated at must be a datetime object")
        return updated_at

    def validate_data(self):
        """Validate all required fields are present and valid"""
        if not self.name:
            raise ValueError("Card name is required")
        if not self.scan_id:
            raise ValueError("Scan ID is required")
        if not self.site_id:
            raise ValueError("Site ID is required")
        if self.price is not None:
            self.validate_price('price', self.price)
