from app.extensions import db
from .base_card import BaseCard
from sqlalchemy.orm import validates
from datetime import datetime, timezone

class UserBuylistCard(BaseCard):
    """
    Maps to user_buylist_card table
    Inherits common card fields from BaseCard
    """
    __tablename__ = "user_buylist_card"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    buylist_id = db.Column(db.Integer, nullable=False)
    buylist_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    @validates('quantity')
    def validate_quantity(self, key, value):
        return value if value is not None else 1

    @validates('quality')
    def validate_quality(self, key, value):
        valid_qualities = ['NM', 'LP', 'MP', 'HP', 'DMG']
        return value if value in valid_qualities else 'NM'

    def to_dict(self):
        """
        Convert to dictionary for API responses
        Include all BaseCard fields from parent class
        """
        base_dict = super().to_dict()
        base_dict.update({
            "id": self.id,
            "buylist_name": self.buylist_name, 
            "set_code": self.set_code, 
            "set_name": self.set_name,
            "language": self.language,
            "quantity": self.quantity,
            "quality": self.quality,
            "version": self.version,
            "foil": self.foil,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        })
        return base_dict

