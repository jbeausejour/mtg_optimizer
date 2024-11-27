from app.extensions import db
from .base_card import BaseCard

class UserBuylistCard(BaseCard):
    __tablename__ = "user_buylist_card"
    id = db.Column(db.Integer, primary_key=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,  # This will use the inherited column
            "set_name": self.set_name,
            "language": self.language,
            "quantity": self.quantity,
            "version": self.version,
            "foil": self.foil,
        }

