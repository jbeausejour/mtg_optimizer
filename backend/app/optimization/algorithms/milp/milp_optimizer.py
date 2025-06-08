from typing import Dict, List
from ...core.base_optimizer import BaseOptimizer, OptimizationResult
import logging

logger = logging.getLogger(__name__)


class MILPOptimizer(BaseOptimizer):
    """MILP optimization algorithm"""

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
                self.find_min_store = config_dict.get("find_min_store", False)
                self.strict_preferences = config_dict.get("strict_preferences", False)

        return MockOptimizationConfig(config)

    def optimize(self) -> OptimizationResult:
        """Run MILP optimization"""
        self._start_timing()

        try:
            # Import the existing PurchaseOptimizer to use its MILP logic
            from ....utils.optimization import PurchaseOptimizer

            # Create PurchaseOptimizer instance
            purchase_optimizer = PurchaseOptimizer(
                self.filtered_listings_df, self.user_wishlist_df, self.optimization_config
            )

            # Run MILP optimization
            best_solution, all_solutions = purchase_optimizer.run_milp_optimization()

            self._end_timing()

            if best_solution is not None:
                # Convert to standardized format
                if hasattr(best_solution, "to_dict"):
                    best_solution_dict = best_solution.to_dict("records")
                else:
                    best_solution_dict = best_solution

                # Create standardized solution
                standardized_solution = purchase_optimizer._create_standardized_solution(best_solution_dict)

                # Format all solutions
                all_solutions_list = []
                if all_solutions:
                    for solution in all_solutions:
                        all_solutions_list.append(solution)

                return OptimizationResult(
                    best_solution=standardized_solution,
                    all_solutions=all_solutions_list,
                    algorithm_used="MILP",
                    execution_time=self.get_execution_time(),
                    iterations=len(all_solutions_list),
                    convergence_metric=0.0,  # MILP finds exact solution
                    performance_stats=self.execution_stats,
                )
            else:
                # Return empty result if no solution found
                return OptimizationResult(
                    best_solution={},
                    all_solutions=[],
                    algorithm_used="MILP",
                    execution_time=self.get_execution_time(),
                    iterations=0,
                    convergence_metric=1.0,  # Failed to converge
                    performance_stats=self.execution_stats,
                )

        except Exception as e:
            logger.error(f"MILP optimization failed: {str(e)}")
            self._end_timing()

            # Return failed result
            return OptimizationResult(
                best_solution={},
                all_solutions=[],
                algorithm_used="MILP",
                execution_time=self.get_execution_time(),
                iterations=0,
                convergence_metric=1.0,
                performance_stats=self.execution_stats,
            )

    def get_algorithm_name(self) -> str:
        return "MILP"
