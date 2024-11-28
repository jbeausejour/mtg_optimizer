from app.extensions import db


class Site(db.Model):
    __tablename__ = "site"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)
    url = db.Column(db.String(255), nullable=False)
    method = db.Column(db.String(50), nullable=False)
    active = db.Column(db.Boolean, default=True)
    type = db.Column(db.String(50), nullable=False)
    country = db.Column(db.String(50), nullable=False)

    # No need to define relationship here as it's defined in ScanResult

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "method": self.method,
            "active": self.active,
            "type": self.type,
            "country": self.country,
        }
