from typing import Dict, List, Type, Optional
import logging
from ..core.base_optimizer import BaseOptimizer

logger = logging.getLogger(__name__)


class OptimizerFactory:
    """Factory for creating optimization algorithms with smart selection"""

    def __init__(self):
        self._algorithms: Dict[str, Type[BaseOptimizer]] = {}
        self._register_default_algorithms()

    def _register_default_algorithms(self):
        """Register default algorithms"""
        try:
            from .milp.milp_optimizer import MILPOptimizer
            from .evolutionary.nsga2_optimizer import ImprovedNSGA2Optimizer
            from .hybrid.milp_moead_hybrid import MILPMOEADHybrid

            self._algorithms.update(
                {
                    "milp": MILPOptimizer,
                    "nsga2": ImprovedNSGA2Optimizer,
                    "hybrid_milp_moead": MILPMOEADHybrid,
                }
            )

            # Try to import MOEA/D if it's implemented
            try:
                from .evolutionary.moead_optimizer import MOEADOptimizer

                self._algorithms["moead"] = MOEADOptimizer
            except ImportError:
                logger.info("MOEA/D optimizer not available yet")

            logger.info(f"Registered {len(self._algorithms)} optimization algorithms")
        except ImportError as e:
            logger.warning(f"Some algorithms failed to load: {e}")

    def register_algorithm(self, name: str, algorithm_class: Type[BaseOptimizer]):
        """Register a new algorithm (for plugins/extensions)"""
        self._algorithms[name] = algorithm_class
        logger.info(f"Registered new algorithm: {name}")

    def create_optimizer(self, algorithm: str, problem_data: Dict, config: Dict) -> BaseOptimizer:
        """Create optimizer instance with validation"""

        if algorithm == "auto":
            algorithm = self._select_best_algorithm(problem_data, config)
            logger.info(f"Auto-selected algorithm: {algorithm}")

        if algorithm not in self._algorithms:
            available = list(self._algorithms.keys())
            raise ValueError(f"Unknown algorithm: {algorithm}. Available: {available}")

        try:
            optimizer_class = self._algorithms[algorithm]
            optimizer = optimizer_class(problem_data, config)

            if not optimizer.validate_input():
                raise ValueError(f"Invalid input data for algorithm: {algorithm}")

            return optimizer

        except Exception as e:
            logger.error(f"Failed to create optimizer {algorithm}: {str(e)}")
            # Fallback to MILP if available
            if algorithm != "milp" and "milp" in self._algorithms:
                logger.info("Falling back to MILP optimizer")
                return self._algorithms["milp"](problem_data, config)
            raise

    def _select_best_algorithm(self, problem_data: Dict, config: Dict) -> str:
        """Automatically select best algorithm based on problem characteristics"""

        # Extract problem characteristics
        problem_size = len(problem_data.get("filtered_listings_df", []))
        num_cards = len(problem_data.get("user_wishlist_df", []))
        num_stores = problem_data.get("num_stores", 10)
        time_limit = config.get("time_limit_seconds", 300)

        logger.info(
            f"Problem characteristics: {problem_size} listings, "
            f"{num_cards} cards, {num_stores} stores, {time_limit}s limit"
        )

        # Decision logic based on research and testing
        if problem_size < 500 and num_cards < 20:
            return "milp"  # Small problems: exact solution
        elif problem_size < 2000 and time_limit > 180:
            return "hybrid_milp_moead" if "hybrid_milp_moead" in self._algorithms else "milp"
        elif "moead" in self._algorithms:
            return "moead"  # Large problems: MOEA/D if available
        else:
            return "nsga2"  # Fallback: improved NSGA-II

    def get_available_algorithms(self) -> List[str]:
        """Get list of available algorithms"""
        return list(self._algorithms.keys())
