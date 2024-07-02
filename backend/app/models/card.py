from backend.app import db

class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    edition = db.Column(db.String(255), nullable=False)
    version = db.Column(db.String(255), nullable=True)
    foil = db.Column(db.Boolean, nullable=False, default=False)
    quality = db.Column(db.String(255), nullable=False)
    language = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'site': self.site,
            'name': self.name,
            'edition': self.edition,
            'version': self.version,
            'foil': self.foil,
            'quality': self.quality,
            'language': self.language,
            'quantity': self.quantity,
            'price': self.price
        }

class Card_list(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False)
    edition = db.Column(db.String(255), nullable=True)
    version = db.Column(db.String(255), nullable=True)
    foil = db.Column(db.Boolean, nullable=True, default=False)
    quality = db.Column(db.String(255), nullable=False)
    language = db.Column(db.String(255), nullable=False, default="English")
    quantity = db.Column(db.Integer, nullable=False, default=1)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'edition': self.edition,
            'version': self.version,
            'foil': self.foil,
            'quality': self.quality,
            'language': self.language,
            'quantity': self.quantity
        }
    
