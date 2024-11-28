from app.extensions import db
from .base_card import BaseCard
from sqlalchemy.orm import validates

class UserBuylistCard(BaseCard):
    """
    Maps to user_buylist_card table
    Inherits common card fields from BaseCard
    """
    __tablename__ = "user_buylist_card"
    id = db.Column(db.Integer, primary_key=True)

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
        return {
            "id": self.id,
            "name": self.name,  # This will use the inherited column
            "set_name": self.set_name,
            "language": self.language,
            "quantity": self.quantity,
            "version": self.version,
            "foil": self.foil,
            "quality": self.quality  # Add quality field
        }

