from app.extensions import db
from datetime import datetime, timezone

class Sets(db.Model):
    __tablename__ = 'sets'
    id = db.Column(db.String(36), primary_key=True)   # Using Scryfall's UUID
    code = db.Column(db.String(10), unique=True, nullable=False)
    tcgplayer_id = db.Column(db.Integer)
    name = db.Column(db.String(255), nullable=False)
    uri = db.Column(db.String(255))
    scryfall_uri = db.Column(db.String(255))
    search_uri = db.Column(db.String(255))
    released_at = db.Column(db.Date)
    set_type = db.Column(db.String(50))
    card_count = db.Column(db.Integer)
    printed_size = db.Column(db.Integer)
    digital = db.Column(db.Boolean, default=False)
    nonfoil_only = db.Column(db.Boolean, default=False)
    foil_only = db.Column(db.Boolean, default=False)
    icon_svg_uri = db.Column(db.String(255))
    last_updated = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    marketplace_cards = db.relationship('MarketplaceCard', back_populates='set')

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'tcgplayer_id': self.tcgplayer_id,
            'name': self.name,
            'uri': self.uri,
            'scryfall_uri': self.scryfall_uri,
            'search_uri': self.search_uri,
            'released_at': self.released_at.isoformat() if self.released_at else None,
            'set_type': self.set_type,
            'card_count': self.card_count,
            'printed_size': self.printed_size,
            'digital': self.digital,
            'nonfoil_only': self.nonfoil_only,
            'foil_only': self.foil_only,
            'icon_svg_uri': self.icon_svg_uri,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }