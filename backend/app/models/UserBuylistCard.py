from datetime import datetime, timezone

from app.extensions import db

from .base_card import BaseCard


class UserBuylistCard(BaseCard):
    """
    Maps to user_buylist_card table
    Inherits common card fields from BaseCard
    """

    __tablename__ = "user_buylist_card"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    buylist_id = db.Column(db.Integer, db.ForeignKey("user_buylist.id"), nullable=False)  # New foreign key
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    def to_dict(self):
        """
        Convert to dictionary for API responses
        Include all BaseCard fields from parent class
        """
        base_dict = super().to_dict()
        base_dict.update(
            {
                "id": self.id,
                "buylist_id": self.buylist_id,
                "user_id": self.user_id,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            }
        )
        return base_dict
