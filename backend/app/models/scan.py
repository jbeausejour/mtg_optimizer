from datetime import datetime, timezone
from app.extensions import db
from .base_card import BaseCard
from sqlalchemy.orm import relationship, validates

class Scan(db.Model):
    __tablename__ = "scan"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    scan_results = relationship("ScanResult", backref="scan", cascade="all, delete-orphan")
    optimization_result = relationship(
        "OptimizationResult",
        uselist=False,
        back_populates="scan",
        cascade="all, delete-orphan",
        overlaps="optimization_results"
    )

    def to_dict(self):
        """Scan metadata and raw results only"""
        result = {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'sites_scraped': len({r.site_id for r in self.scan_results}),
            'cards_scraped': len({r.name for r in self.scan_results}),
            'scan_results': [result.to_dict() for result in self.scan_results],
            'optimization_result': self.optimization_result.to_dict() if self.optimization_result else None
        }
        return result

class ScanResult(BaseCard):
    """Raw card data from scraping"""
    __tablename__ = "scan_result"
    id = db.Column(db.Integer, primary_key=True)
    scan_id = db.Column(db.Integer, db.ForeignKey('scan.id'))
    site_id = db.Column(db.Integer, db.ForeignKey('site.id'))
    price = db.Column(db.Float)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    site = relationship('Site', backref='scan_results')

    def to_dict(self):
        return {
            'id': self.id,
            'scan_id': self.scan_id,
            'site_id': self.site_id,
            'name': self.name,
            'price': float(self.price),
            'quality': self.quality,
            'quantity': self.quantity,
            'set_name': self.set_name,
            'set_code': self.set_code,
            'language': self.language,
            'version': self.version,
            'site_name': self.site.name if self.site else None
        }


    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validate_data()

    @validates('price')
    def validate_price(self, key, price):
        if price is not None and float(price) < 0:
            raise ValueError("Price cannot be negative")
        return price

    @validates('scan_id', 'site_id')
    def validate_ids(self, key, value):
        if not value:
            raise ValueError(f"{key} is required")
        return value

    @validates('updated_at')
    def validate_updated_at(self, key, updated_at):
        if updated_at and not isinstance(updated_at, datetime):
            raise ValueError("Updated at must be a datetime object")
        return updated_at

    def validate_data(self):
        if not self.name:
            raise ValueError("Card name is required")
        if not self.scan_id:
            raise ValueError("Scan ID is required")
        if not self.site_id:
            raise ValueError("Site ID is required")
        if self.price is not None:
            self.validate_price('price', self.price)