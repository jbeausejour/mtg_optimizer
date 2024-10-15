from app.extensions import db

class UserBuylistCard(db.Model):
    __tablename__ = "user_buylist_card"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)  # Only store the name to fetch from Scryfall
    quantity = db.Column(db.Integer, nullable=False, default=1)
    foil = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "quantity": self.quantity,
            "foil": self.foil,
        }

