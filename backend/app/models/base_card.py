from datetime import datetime
from app.extensions import db

class BaseCard(db.Model):
    """Abstract base class for card-related models"""
    __abstract__ = True
    
    name = db.Column(db.String(255), nullable=False)  # This already defines the name column
    set_name = db.Column(db.String(255))
    language = db.Column(db.String(50), default="English")
    version = db.Column(db.String(255), default="Standard")
    foil = db.Column(db.Boolean, default=False)
    quantity = db.Column(db.Integer, default=0)