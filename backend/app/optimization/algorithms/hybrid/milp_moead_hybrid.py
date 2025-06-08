from typing import Dict
from ...core.base_optimizer import BaseOptimizer, OptimizationResult
from ..milp.milp_optimizer import MILPOptimizer
import logging

logger = logging.getLogger(__name__)


class MILPMOEADHybrid(BaseOptimizer):
    """Hybrid MILP + MOEA/D optimizer (currently MILP + NSGA-II until MOEA/D is implemented)"""

    def __init__(self, problem_data: Dict, config: Dict):
        super().__init__(problem_data, config)
        self.filtered_listings_df = problem_data["filtered_listings_df"]
        self.user_wishlist_df = problem_data["user_wishlist_df"]

    def optimize(self) -> OptimizationResult:
        """Hybrid optimization strategy"""
        self._start_timing()

        try:
            # Phase 1: Quick MILP for feasibility and seeding
            logger.info("Phase 1: Running MILP optimization")
            milp_optimizer = MILPOptimizer(self.problem_data, self.config)
            milp_result = milp_optimizer.optimize()

            # Phase 2: NSGA-II with MILP seeding (until MOEA/D is implemented)
            logger.info("Phase 2: Running NSGA-II optimization with MILP seeding")

            # Use existing PurchaseOptimizer for hybrid approach
            from ....utils.optimization import PurchaseOptimizer

            # Create mock config
            class MockOptimizationConfig:
                def __init__(self, config_dict):
                    self.weights = config_dict.get("weights", {})
                    self.min_store = config_dict.get("min_store", 1)
                    self.max_store = config_dict.get("max_store", 10)
                    self.max_unique_store = config_dict.get("max_unique_store", 10)
                    self.strict_preferences = config_dict.get("strict_preferences", False)
                    self.hybrid_strat = True
                    self.milp_strat = True
                    self.nsga_strat = True

            optimization_config = MockOptimizationConfig(self.config)

            # Create PurchaseOptimizer and run hybrid optimization
            purchase_optimizer = PurchaseOptimizer(
                self.filtered_listings_df, self.user_wishlist_df, optimization_config
            )

            # Extract card names
            card_names = self.user_wishlist_df["name"].tolist()

            # Run the hybrid optimization
            result = purchase_optimizer.run_optimization(card_names, optimization_config)

            self._end_timing()

            if result and result.get("status") == "success":
                return OptimizationResult(
                    best_solution=result.get("best_solution", {}),
                    all_solutions=result.get("iterations", []),
                    algorithm_used="Hybrid-MILP-NSGA2",
                    execution_time=self.get_execution_time(),
                    iterations=len(result.get("iterations", [])),
                    convergence_metric=0.0,
                    performance_stats=self.execution_stats,
                )
            else:
                # Fallback to MILP result if hybrid fails
                logger.warning("Hybrid optimization failed, using MILP result")
                return milp_result

        except Exception as e:
            logger.error(f"Hybrid optimization failed: {str(e)}")
            self._end_timing()

            return OptimizationResult(
                best_solution={},
                all_solutions=[],
                algorithm_used="Hybrid-MILP-NSGA2",
                execution_time=self.get_execution_time(),
                iterations=0,
                convergence_metric=1.0,
                performance_stats=self.execution_stats,
            )

    def get_algorithm_name(self) -> str:
        return "Hybrid-MILP-NSGA2"
