from ..optimization.algorithms.factory import OptimizerFactory
from ..optimization.config.algorithm_configs import AlgorithmConfig
import logging

logger = logging.getLogger(__name__)


class EnhancedOptimizationService:
    """New service using modular architecture"""

    def __init__(self):
        self.optimizer_factory = OptimizerFactory()

    async def optimize_card_purchase(self, session, listings_df, wishlist_df, config, celery_task=None):
        """Main optimization entry point"""

        try:
            # Convert old config to new format
            algorithm_config = AlgorithmConfig.from_optimization_config(config)

            # Prepare problem data
            problem_data = {
                "filtered_listings_df": listings_df,
                "user_wishlist_df": wishlist_df,
                "num_stores": listings_df["site_name"].nunique(),
            }

            # Create and run optimizer
            optimizer = self.optimizer_factory.create_optimizer(
                algorithm_config.primary_algorithm, problem_data, algorithm_config.to_dict()
            )

            # Update progress if celery task provided
            if celery_task:
                celery_task.update_state(
                    state="PROCESSING",
                    meta={"status": f"Running {optimizer.get_algorithm_name()} optimization", "progress": 75},
                )

            result = optimizer.optimize()

            # Convert to expected format for backward compatibility
            return self._format_for_existing_system(result)

        except Exception as e:
            logger.error(f"Enhanced optimization service failed: {str(e)}")
            raise

    def _format_for_existing_system(self, result):
        """Convert OptimizationResult to format expected by existing system"""
        return {
            "status": "success" if result.best_solution else "failed",
            "best_solution": result.best_solution,
            "iterations": result.all_solutions,
            "algorithm_used": result.algorithm_used,
            "execution_time": result.execution_time,
            "type": result.algorithm_used.lower().replace("-", "_"),
        }
