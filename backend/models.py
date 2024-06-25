from app import db

class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    url = db.Column(db.String(255), unique=True, nullable=False)
    parse_method = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(10), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'parse_method': self.parse_method,
            'type': self.type
        }

class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Site = db.Column(db.String(255), nullable=False)
    Name = db.Column(db.String(255), nullable=False)
    Edition = db.Column(db.String(255), nullable=False)
    Version = db.Column(db.String(255), nullable=True)
    Foil = db.Column(db.Boolean, nullable=False, default=False)
    Quality = db.Column(db.String(255), nullable=False)
    Language = db.Column(db.String(255), nullable=False)
    Quantity = db.Column(db.Integer, nullable=False)
    Price = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            'Site': self.Site,
            'Name': self.Name,
            'Edition': self.Edition,
            'Version': self.Version,
            'Foil': self.Foil,
            'Quality': self.Quality,
            'Language': self.Language,
            'Quantity': self.Quantity,
            'Price': self.Price
        }

    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return (
            (self.Site, self.Name, self.Edition, self.Version, self.Foil, self.Quality, self.Language, self.Quantity, self.Price) ==
            (other.Site, other.Name, other.Edition, other.Version, other.Foil, other.Quality, other.Language, other.Quantity, other.Price)
        )

    def __hash__(self):
        return hash((self.Site, self.Name, self.Edition, self.Version, self.Foil, self.Quality, self.Language, self.Quantity, self.Price))


class CardScan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    scan_data = db.Column(db.JSON, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'scan_data': self.scan_data
        }
