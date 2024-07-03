from app import db

class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    url = db.Column(db.String(255), unique=True, nullable=False)
    method = db.Column(db.String(50), nullable=False)
    active = db.Column(db.Boolean, nullable=False)
    country = db.Column(db.String(50), nullable=False)
    type = db.Column(db.String(50), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'method': self.method,
            'active': self.active,
            'country': self.country,
            'type': self.type
        }