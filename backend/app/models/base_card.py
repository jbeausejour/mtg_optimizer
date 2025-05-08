import re
from datetime import datetime
from venv import logger

from sqlalchemy import Column, String, Boolean, Integer
from sqlalchemy.orm import validates

from app.constants.card_mappings import CardLanguage, CardQuality, CardVersion
from app import Base


class BaseCard(Base):
    """Abstract base class for card-related models"""

    __abstract__ = True

    name = Column(String(255), nullable=False)
    set_name = Column(String(255), nullable=True)
    set_code = Column(String(10), nullable=True)
    language = Column(String(50), nullable=True, default="English")
    version = Column(String(255), nullable=True, default="Standard")
    foil = Column(Boolean, nullable=True, default=False)
    quantity = Column(Integer, nullable=True, default=0)
    quality = Column(String(50), nullable=True, default="NM")

    @validates("name")
    def validate_name(self, key, name):
        """Ensure name is provided and not empty"""
        if not name or not name.strip():
            raise ValueError("Card name is required")
        return name.strip()

    @validates("language")
    def validate_language(self, key, value):
        """Validate card language"""
        normalized = CardLanguage.normalize(value)
        if normalized not in {lang.value for lang in CardLanguage}:
            valid_languages = sorted({lang.value for lang in CardLanguage})
            logger.error(f"Invalid language : {value}")
            raise ValueError(f"Invalid language. Must be one of: {', '.join(valid_languages)}")
        return normalized

    @validates("set_code")
    def validate_set_code(self, key, set_code):
        """Ensure set_code follows MTG standard format"""
        if set_code and not re.match(r"^[a-zA-Z0-9]{3,5}$", set_code):
            logger.error(f"Invalid set code format: {set_code}")
            raise ValueError(f"Invalid set code format: {set_code}")
        return set_code.upper() if set_code else None

    @validates("quality")
    def validate_quality(self, key, quality):
        """Validate card quality"""
        try:
            return CardQuality.validate_and_normalize(quality) if quality else CardQuality.NM.value
        except ValueError as e:
            valid_qualities = ", ".join(q.value for q in CardQuality)
            raise ValueError(f"Invalid quality. Must be one of: {valid_qualities}")

    @validates("version")
    def validate_version(self, key, version):
        """Validate card version"""
        if not version:
            return CardVersion.STANDARD.value

        if version not in {v.value for v in CardVersion}:
            valid_versions = ", ".join(v.value for v in CardVersion)
            raise ValueError(f"Invalid version. Must be one of: {valid_versions}")
        return version

    @validates("quantity")
    def validate_quantity(self, key, quantity):
        """Validate quantity is non-negative"""
        if quantity is not None and int(quantity) < 0:
            raise ValueError("Quantity cannot be negative")
        return int(quantity) if quantity is not None else 0

    def to_dict(self):
        """Base to_dict method for all card models"""
        return {
            "name": self.name,
            "set_name": self.set_name,
            "set_code": self.set_code,
            "language": self.language,
            "version": self.version,
            "foil": self.foil,
            "quantity": self.quantity,
            "quality": self.quality,
        }
