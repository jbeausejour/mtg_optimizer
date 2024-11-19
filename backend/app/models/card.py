from app.extensions import db

class UserBuylistCard(db.Model):
    __tablename__ = "user_buylist_card"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    set = db.Column(db.String)
    language = db.Column(db.String, default="English")
    quantity = db.Column(db.Integer, default=1)
    version = db.Column(db.String, default="Standard")
    foil = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "set": self.set,
            "language": self.language,
            "quantity": self.quantity,
            "version": self.version,
            "foil": self.foil,
        }

