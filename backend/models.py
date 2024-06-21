from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    url = db.Column(db.String(200), nullable=False)
    parse_method = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(10), nullable=True)

    def __repr__(self):
        return f'<Site {self.name}>'
