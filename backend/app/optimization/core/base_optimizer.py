from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Standardized optimization result"""

    best_solution: Dict
    all_solutions: List[Dict]
    algorithm_used: str
    execution_time: float
    iterations: int
    convergence_metric: float
    performance_stats: Dict


class BaseOptimizer(ABC):
    """Abstract base class for all optimization algorithms"""

    def __init__(self, problem_data: Dict, config: Dict):
        self.problem_data = problem_data
        self.config = config
        self.execution_stats = {"start_time": None, "end_time": None, "evaluations": 0, "iterations": 0}

    @abstractmethod
    def optimize(self) -> OptimizationResult:
        """Run optimization and return standardized result"""
        pass

    @abstractmethod
    def get_algorithm_name(self) -> str:
        """Return algorithm identifier"""
        pass

    def validate_input(self) -> bool:
        """Validate input data and configuration"""
        required_keys = ["filtered_listings_df", "user_wishlist_df"]
        return all(key in self.problem_data for key in required_keys)

    def _start_timing(self):
        """Start execution timing"""
        self.execution_stats["start_time"] = time.time()

    def _end_timing(self):
        """End execution timing"""
        self.execution_stats["end_time"] = time.time()

    def get_execution_time(self) -> float:
        """Get total execution time"""
        if self.execution_stats["start_time"] and self.execution_stats["end_time"]:
            return self.execution_stats["end_time"] - self.execution_stats["start_time"]
        return 0.0
