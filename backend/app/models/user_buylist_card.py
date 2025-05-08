from datetime import datetime, timezone
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from app.models.base_card import BaseCard


class UserBuylistCard(BaseCard):
    """
    Maps to user_buylist_card table
    Inherits common card fields from BaseCard
    """

    __tablename__ = "user_buylist_card"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    buylist_id = Column(Integer, ForeignKey("user_buylist.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
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
