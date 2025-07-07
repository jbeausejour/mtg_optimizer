from datetime import datetime, timezone

from sqlalchemy import Column, Float, Integer, String, JSON, DateTime, ForeignKey
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
    algorithm_used = Column(String, nullable=True)
    execution_time = Column(Float, nullable=True)
    performance_stats = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    scan = relationship("Scan", back_populates="optimization_result")

    def to_dict(self):
        """Enhanced dictionary representation of the model including new fields"""
        return {
            "id": self.id,
            "scan_id": self.scan_id,
            "status": self.status,
            "message": self.message,
            "sites_scraped": self.sites_scraped,
            "cards_scraped": self.cards_scraped,
            "solutions": self.solutions,
            "errors": self.errors,
            "algorithm_used": self.algorithm_used,
            "execution_time": self.execution_time,
            "performance_stats": self.performance_stats,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_dict_enhanced(self):
        """Enhanced version with additional computed fields for the frontend"""
        base_dict = self.to_dict()

        # Add computed fields that the frontend might find useful
        if self.solutions:
            # Find the best solution
            best_solution = None
            for solution in self.solutions:
                if isinstance(solution, dict) and solution.get("is_best_solution"):
                    best_solution = solution
                    break

            if best_solution:
                base_dict["best_solution"] = best_solution

                # Add summary statistics
                base_dict["summary_stats"] = {
                    "completion_rate": (
                        (
                            best_solution.get("nbr_card_in_solution", 0)
                            / max(best_solution.get("cards_required_total", 1), 1)
                        )
                        * 100
                    ),
                    "is_complete": best_solution.get("missing_cards_count", 1) == 0,
                    "total_stores": best_solution.get("number_store", 0),
                    "total_cost": best_solution.get("total_price", 0.0),
                }

        # Add performance metrics if available
        if self.performance_stats and self.execution_time:
            base_dict["performance_score"] = self._calculate_performance_score()

        return base_dict

    def _calculate_performance_score(self):
        """Calculate a performance score based on execution time and solution quality"""
        if not self.performance_stats or not self.execution_time:
            return None

        # Find best solution for quality calculation
        best_solution = None
        if self.solutions:
            for solution in self.solutions:
                if isinstance(solution, dict) and solution.get("is_best_solution"):
                    best_solution = solution
                    break

        if not best_solution:
            return None

        # Calculate completion rate
        completion_rate = (
            best_solution.get("nbr_card_in_solution", 0) / max(best_solution.get("cards_required_total", 1), 1)
        ) * 100

        # Time score (normalize by 3 seconds - faster is better)
        time_score = max(0, 100 - (self.execution_time / 3.0))

        # Quality score is the completion rate
        quality_score = completion_rate

        # Combined score (weighted average)
        performance_score = round((time_score + quality_score) / 2)

        return performance_score
