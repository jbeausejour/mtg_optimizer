from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app import Base


class OptimizationResult(Base):
    __tablename__ = "optimization_results"

    id = Column(Integer, primary_key=True)
    scan_id = Column(Integer, ForeignKey("scan.id"), nullable=False)
    status = Column(String(50), nullable=False)
    message = Column(String(255))
    sites_scraped = Column(Integer)
    cards_scraped = Column(Integer)
    solutions = Column(JSON)
    errors = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    scan = relationship("Scan", back_populates="optimization_result")

    def to_dict(self):
        """Basic dictionary representation of the model"""
        return {
            "id": self.id,
            "scan_id": self.scan_id,
            "status": self.status,
            "message": self.message,
            "sites_scraped": self.sites_scraped,
            "cards_scraped": self.cards_scraped,
            "solutions": self.solutions,
            "errors": self.errors,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
