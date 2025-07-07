# backend/app/optimization/core/base_optimizer.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
import time
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Standard result format for all optimizers"""

    best_solution: Dict[str, Any]
    all_solutions: list[Dict[str, Any]]
    algorithm_used: str
    execution_time: float
    iterations: int
    convergence_metric: float
    performance_stats: Dict[str, Any]
    errors: Optional[Dict[str, list[str]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "best_solution": self.best_solution,
            "all_solutions": self.all_solutions,
            "algorithm_used": self.algorithm_used,
            "execution_time": self.execution_time,
            "iterations": self.iterations,
            "convergence_metric": self.convergence_metric,
            "performance_stats": self.performance_stats,
            "errors": self.errors or {"unreachable_stores": [], "unknown_languages": [], "unknown_qualities": []},
        }


class BaseOptimizer(ABC):
    """Abstract base class for all optimization algorithms"""

    def __init__(self, problem_data: Dict[str, Any], config: Dict[str, Any]):
        """
        Initialize optimizer

        Args:
            problem_data: Dictionary containing:
                - filtered_listings_df: DataFrame with card listings
                - user_wishlist_df: DataFrame with user requirements
                - num_stores: Number of available stores
            config: Algorithm configuration parameters
        """
        self.problem_data = problem_data
        self.config = config

        # Extract common data
        self.listings_df = problem_data.get("filtered_listings_df")
        self.user_wishlist_df = problem_data.get("user_wishlist_df")
        self.num_stores = problem_data.get("num_stores", 0)

        # Configuration
        self.time_limit = config.get("time_limit", 300)
        self.max_iterations = config.get("max_iterations", 1000)
        self.early_stopping = config.get("early_stopping", True)
        self.convergence_threshold = config.get("convergence_threshold", 0.001)

        # Store constraints
        self.min_stores = config.get("min_store", 1)
        self.max_stores = config.get("max_store", 10)
        self.find_min_store = config.get("find_min_store", False)

        # Weights
        self.weights = config.get("weights", {"cost": 1.0, "quality": 1.0, "store_count": 0.3})

        # Progress tracking
        self.progress_callback: Optional[Callable[[float, str], None]] = None
        self.start_time = None
        self.end_time = None

        # Execution statistics
        self.execution_stats = {}

    def set_progress_callback(self, callback: Callable[[float, str], None]):
        """Set callback for progress updates"""
        self.progress_callback = callback

    def _update_progress(self, progress: float, message: str):
        """Update progress if callback is set"""
        if self.progress_callback:
            self.progress_callback(progress, message)

    def _start_timing(self):
        """Start timing the optimization"""
        self.start_time = time.time()
        self.execution_stats["start_time"] = self.start_time

    def _end_timing(self):
        """End timing and calculate execution time"""
        self.end_time = time.time()
        self.execution_stats["end_time"] = self.end_time
        self.execution_stats["execution_time"] = self.end_time - self.start_time

    def get_execution_time(self) -> float:
        """Get execution time"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    @abstractmethod
    def optimize(self) -> OptimizationResult:
        """
        Run optimization - must be implemented by subclasses

        Returns:
            OptimizationResult with standardized format
        """
        pass

    @abstractmethod
    def get_algorithm_name(self) -> str:
        """Get human-readable algorithm name"""
        pass

    def _get_errors(self) -> Dict[str, list[str]]:
        """Get errors from error collector if available"""
        try:
            from app.utils.data_fetcher import ErrorCollector

            error_collector = ErrorCollector.get_instance()
            return {
                "unreachable_stores": list(error_collector.unreachable_stores),
                "unknown_languages": list(error_collector.unknown_languages),
                "unknown_qualities": list(error_collector.unknown_qualities),
            }
        except:
            return {
                "unreachable_stores": [],
                "unknown_languages": [],
                "unknown_qualities": [],
            }

    @classmethod
    def validate_config(cls, config: Dict[str, Any]) -> bool:
        """
        Validate configuration parameters

        Args:
            config: Configuration dictionary

        Returns:
            True if config is valid
        """
        required = ["time_limit", "max_iterations"]
        return all(param in config for param in required)

    @classmethod
    def get_parameter_info(cls) -> Dict[str, Any]:
        """
        Get information about algorithm parameters

        Returns:
            Dictionary with parameter descriptions
        """
        return {
            "time_limit": {"type": "int", "default": 300, "description": "Maximum time in seconds"},
            "max_iterations": {"type": "int", "default": 1000, "description": "Maximum number of iterations"},
            "early_stopping": {"type": "bool", "default": True, "description": "Enable early stopping on convergence"},
            "convergence_threshold": {
                "type": "float",
                "default": 0.001,
                "description": "Relative change threshold for convergence",
            },
        }
