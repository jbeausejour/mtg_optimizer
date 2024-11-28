from datetime import datetime
from app.extensions import db
from sqlalchemy.orm import validates

class BaseCard(db.Model):
    """Abstract base class for card-related models"""
    __abstract__ = True  # This ensures BaseCard won't create its own table
    
    name = db.Column(db.String(255), nullable=False)  # This already defines the name column
    set_name = db.Column(db.String(255), nullable=True)
    language = db.Column(db.String(50), nullable=True, default="English")
    version = db.Column(db.String(255), nullable=True, default="Standard")
    foil = db.Column(db.Boolean, nullable=True, default=False)
    quantity = db.Column(db.Integer, nullable=True, default=0)
    quality = db.Column(db.String(50), nullable=True, default="NM")  # Add quality column

    @validates('name')
    def validate_name(self, key, name):
        """Ensure name is provided and not empty"""
        if not name or not name.strip():
            raise ValueError("Card name is required")
        return name.strip()

    @validates('language')
    def validate_language(self, key, language):
        """Validate language"""
        valid_languages = ["English", "Japanese", "Chinese", "Korean", "Russian", "German", "Spanish", "French", "Italian", "Portuguese"]
        if language and language not in valid_languages:
            raise ValueError(f"Invalid language. Must be one of: {', '.join(valid_languages)}")
        return language or "English"

    @validates('quality')
    def validate_quality(self, key, quality):
        """Validate card quality"""
        valid_qualities = ['NM', 'LP', 'MP', 'HP', 'DMG']
        if quality and quality not in valid_qualities:
            raise ValueError(f"Invalid quality. Must be one of: {', '.join(valid_qualities)}")
        return quality or "NM"

    @validates('quantity')
    def validate_quantity(self, key, quantity):
        """Validate quantity is non-negative"""
        if quantity is not None and int(quantity) < 0:
            raise ValueError("Quantity cannot be negative")
        return int(quantity) if quantity is not None else 0

    def to_dict(self):
        """Base to_dict method for all card models"""
        return {
            "name": self.name,
            "set_name": self.set_name,
            "language": self.language,
            "version": self.version,
            "foil": self.foil,
            "quantity": self.quantity,
            "quality": self.quality
        }