from sqlalchemy import Column, String, Integer, Boolean
from app import Base


class Site(Base):
    __tablename__ = "site"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    url = Column(String(255), nullable=False)
    method = Column(String(50), nullable=False)
    api_url = Column(String(255))
    active = Column(Boolean, default=True)
    type = Column(String(50), nullable=False)
    country = Column(String(50), nullable=False)

    # No need to define relationship here as it's defined in ScanResult

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "method": self.method,
            "api_url": self.api_url,
            "active": self.active,
            "type": self.type,
            "country": self.country,
        }
