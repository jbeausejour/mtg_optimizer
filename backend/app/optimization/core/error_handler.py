# backend/app/optimization/core/error_handler.py
import logging
import traceback
from typing import Dict, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class OptimizationErrorHandler:
    """Enhanced error handling for optimization processes"""

    @staticmethod
    @contextmanager
    def handle_optimization_errors(operation_name: str = "optimization"):
        """Context manager for handling optimization errors gracefully"""
        try:
            yield
        except ImportError as e:
            logger.error(f"Missing dependency for {operation_name}: {str(e)}")
            raise ValueError(f"Required package not available: {str(e)}")
        except ValueError as e:
            logger.error(f"Configuration error in {operation_name}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {operation_name}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise RuntimeError(f"Optimization failed: {str(e)}")

    @staticmethod
    def create_safe_optimization_result(
        algorithm_name: str, error_message: str, execution_time: float = 0.0
    ) -> Dict[str, Any]:
        """Create a safe result when optimization fails"""
        return {
            "status": "Failed",
            "message": f"Optimization failed: {error_message}",
            "algorithm_used": algorithm_name,
            "execution_time": execution_time,
            "best_solution": {},
            "all_solutions": [],
            "iterations": 0,
            "convergence_metric": 1.0,
            "performance_stats": {"error": error_message, "execution_time": execution_time},
        }

    @staticmethod
    def validate_problem_data(problem_data: Dict) -> bool:
        """Validate problem data before optimization"""
        required_keys = ["filtered_listings_df", "user_wishlist_df"]

        for key in required_keys:
            if key not in problem_data:
                logger.error(f"Missing required problem data: {key}")
                return False

            if problem_data[key] is None:
                logger.error(f"Problem data {key} is None")
                return False

            # Check if DataFrame is empty
            if hasattr(problem_data[key], "empty") and problem_data[key].empty:
                logger.error(f"Problem data {key} is empty")
                return False

        return True

    @staticmethod
    def sanitize_config(config: Dict) -> Dict:
        """Sanitize and set default values for configuration"""
        sanitized = config.copy()

        # Ensure required weights exist
        if "weights" not in sanitized:
            sanitized["weights"] = {"cost": 1.0, "quality": 1.0, "store_count": 0.3}

        # Ensure store constraints are valid
        if "min_store" not in sanitized:
            sanitized["min_store"] = 1
        if "max_store" not in sanitized:
            sanitized["max_store"] = 10

        # Fix max_store if it's invalid
        if sanitized["max_store"] < sanitized["min_store"]:
            sanitized["max_store"] = sanitized["min_store"]

        # Set safe defaults for evolutionary algorithms
        if "population_size" not in sanitized:
            sanitized["population_size"] = 100
        if "max_generations" not in sanitized:
            sanitized["max_generations"] = 100

        return sanitized


# Usage example in optimization tasks:
def safe_optimization_wrapper(optimization_func):
    """Decorator for safe optimization execution"""

    def wrapper(*args, **kwargs):
        try:
            with OptimizationErrorHandler.handle_optimization_errors("optimization"):
                return optimization_func(*args, **kwargs)
        except Exception as e:
            algorithm_name = kwargs.get("algorithm", "unknown")
            return OptimizationErrorHandler.create_safe_optimization_result(algorithm_name, str(e))

    return wrapper
