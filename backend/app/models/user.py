from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship
from werkzeug.security import check_password_hash, generate_password_hash
from app import Base


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), index=True, unique=True)
    email = Column(String(120), index=True, unique=True)
    password_hash = Column(String(128))
    buylist_cards = relationship("UserBuylistCard", backref="user", lazy="selectin", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "buylist_cards": [card.to_dict() for card in self.buylist_cards],
        }
