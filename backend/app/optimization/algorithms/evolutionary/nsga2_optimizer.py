from typing import Dict, List
from ...core.base_optimizer import BaseOptimizer, OptimizationResult
import logging

logger = logging.getLogger(__name__)


class ImprovedNSGA2Optimizer(BaseOptimizer):
    """Improved NSGA-II implementation"""

    def __init__(self, problem_data: Dict, config: Dict):
        super().__init__(problem_data, config)

        # Extract data from problem_data
        self.filtered_listings_df = problem_data["filtered_listings_df"]
        self.user_wishlist_df = problem_data["user_wishlist_df"]

        # Create a mock optimization config for compatibility
        self.optimization_config = self._create_optimization_config(config)

    def _create_optimization_config(self, config: Dict):
        """Create a mock optimization config object for backward compatibility"""

        class MockOptimizationConfig:
            def __init__(self, config_dict):
                self.weights = config_dict.get(
                    "weights", {"cost": 1.0, "quality": 1.0, "availability": 100.0, "store_count": 0.3}
                )
                self.min_store = config_dict.get("min_store", 1)
                self.max_store = config_dict.get("max_store", 10)
                self.max_unique_store = config_dict.get("max_unique_store", 10)
                self.strict_preferences = config_dict.get("strict_preferences", False)

        return MockOptimizationConfig(config)

    def optimize(self) -> OptimizationResult:
        """Run improved NSGA-II optimization"""
        self._start_timing()

        try:
            # Import the existing PurchaseOptimizer to use its NSGA-II logic
            from ....utils.optimization import PurchaseOptimizer

            # Create PurchaseOptimizer instance
            purchase_optimizer = PurchaseOptimizer(
                self.filtered_listings_df, self.user_wishlist_df, self.optimization_config
            )

            # Run NSGA-II optimization
            best_solution, all_solutions = purchase_optimizer.run_nsga_ii_optimization()

            self._end_timing()

            if best_solution is not None:
                # All solutions should already be in standardized format
                all_solutions_list = all_solutions if all_solutions else []

                return OptimizationResult(
                    best_solution=best_solution,
                    all_solutions=all_solutions_list,
                    algorithm_used="NSGA-II-Improved",
                    execution_time=self.get_execution_time(),
                    iterations=len(all_solutions_list),
                    convergence_metric=0.0,  # Successful convergence
                    performance_stats=self.execution_stats,
                )
            else:
                # Return empty result if no solution found
                return OptimizationResult(
                    best_solution={},
                    all_solutions=[],
                    algorithm_used="NSGA-II-Improved",
                    execution_time=self.get_execution_time(),
                    iterations=0,
                    convergence_metric=1.0,  # Failed to converge
                    performance_stats=self.execution_stats,
                )

        except Exception as e:
            logger.error(f"NSGA-II optimization failed: {str(e)}")
            self._end_timing()

            # Return failed result
            return OptimizationResult(
                best_solution={},
                all_solutions=[],
                algorithm_used="NSGA-II-Improved",
                execution_time=self.get_execution_time(),
                iterations=0,
                convergence_metric=1.0,
                performance_stats=self.execution_stats,
            )

    def get_algorithm_name(self) -> str:
        return "NSGA-II-Improved"
