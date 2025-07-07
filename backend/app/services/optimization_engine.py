# backend/app/services/enhanced_optimization_service.py
from typing import Dict, List, Optional, Any
import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from ..optimization.algorithms.factory import OptimizerFactory
from ..optimization.config.algorithm_configs import AlgorithmConfig
from ..optimization.core.metrics import OptimizationMetrics

logger = logging.getLogger(__name__)


class OptimizationEngine:
    """
    Enhanced optimization service using the new modular architecture.

    Features:
    - Algorithm auto-selection based on problem characteristics
    - NSGA-III support for complex multi-objective problems
    - Performance tracking and metrics
    - Caching of optimization results
    - Progress tracking for long-running optimizations
    """

    def __init__(self):
        self.optimizer_factory = OptimizerFactory()
        self.metrics_tracker = OptimizationMetrics()
        self._result_cache = {}
        self._cache_max_size = 100

    async def optimize_card_purchase(
        self, session: AsyncSession, listings_df, user_wishlist_df, config, celery_task_updater=None
    ) -> Dict:
        """
        Main optimization entry point with enhanced features and NSGA-III support.

        Args:
            session: Database session
            listings_df: DataFrame with card listings
            user_wishlist_df: DataFrame with user wishlist
            config: Optimization configuration (can be dict or OptimizationConfigDTO)
            celery_task_updater: Optional Celery helper class that can update task state using the captured ID

        Returns:
            Optimization result in standardized format
        """
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(user_wishlist_df, config)

            # Check cache first
            if cache_key in self._result_cache:
                logger.info("Returning cached optimization result")
                return self._result_cache[cache_key]

            # Convert config to AlgorithmConfig
            if hasattr(config, "to_dict"):
                # It's a DTO
                algorithm_config = AlgorithmConfig.from_optimization_config(config)
            else:
                # It's a dict from frontend
                algorithm_config = self._create_algorithm_config_from_frontend(config)

            # Auto-select algorithm if requested
            if algorithm_config.primary_algorithm == "auto":
                algorithm_config.primary_algorithm = self._select_best_algorithm(listings_df, user_wishlist_df, config)
                logger.info(f"Auto-selected algorithm: {algorithm_config.primary_algorithm}")

            # Prepare problem data
            problem_data = {
                "filtered_listings_df": listings_df,
                "user_wishlist_df": user_wishlist_df,
                "num_stores": listings_df["site_name"].nunique(),
            }

            # Add problem characteristics for metrics
            problem_characteristics = self._analyze_problem_characteristics(listings_df, user_wishlist_df)

            # Create and configure optimizer
            optimizer = self.optimizer_factory.create_optimizer(
                algorithm_config.primary_algorithm, problem_data, algorithm_config.to_dict()
            )

            # Set up progress tracking
            if celery_task_updater:
                self._setup_progress_tracking(optimizer, celery_task_updater)

            # Run optimization
            logger.info(f"Starting {optimizer.get_algorithm_name()} optimization")
            logger.info(f"Configuration: {algorithm_config.to_dict()}")

            result = await self._run_optimization_async(optimizer)

            # Record metrics
            self.metrics_tracker.record_optimization(
                algorithm=result.algorithm_used,
                execution_time=result.execution_time,
                solution_quality=self._calculate_solution_quality(result),
                problem_size=len(user_wishlist_df),
                problem_characteristics=problem_characteristics,
            )

            # Convert to expected format for backward compatibility
            formatted_result = self._format_for_existing_system(result)

            # Cache result
            self._add_to_cache(cache_key, formatted_result)

            # Log performance summary
            self._log_optimization_summary(result, problem_characteristics)

            return formatted_result

        except Exception as e:
            logger.error(f"Enhanced optimization service failed: {str(e)}")
            raise

    def _create_algorithm_config_from_frontend(self, config: Dict) -> AlgorithmConfig:
        """Create AlgorithmConfig from frontend parameters with NSGA-III support"""
        # Handle both old-style and new-style configs
        primary_algorithm = config.get("primary_algorithm") or config.get("strategy", "milp")

        # Create base config
        algorithm_config = AlgorithmConfig(
            primary_algorithm=primary_algorithm,
            min_store=config.get("min_store", 1),
            max_store=config.get("max_store", 10),
            find_min_store=config.get("find_min_store", False),
            strict_preferences=config.get("strict_preferences", False),
            weights=config.get("weights", {"cost": 1.0, "quality": 1.0, "store_count": 0.3}),
            user_preferences=config.get("user_preferences", {}),
            time_limit=config.get("time_limit", 300),
            max_iterations=config.get("max_iterations", 1000),
            early_stopping=config.get("early_stopping", True),
            convergence_threshold=config.get("convergence_threshold", 0.001),
        )

        # Add algorithm-specific parameters
        if primary_algorithm in ["nsga2", "moead", "nsga3"]:
            algorithm_config.population_size = config.get("population_size", 200)

        if primary_algorithm == "nsga3":
            algorithm_config.reference_point_divisions = config.get("reference_point_divisions", 12)

        if primary_algorithm == "moead":
            algorithm_config.neighborhood_size = config.get("neighborhood_size", 20)
            algorithm_config.decomposition_method = config.get("decomposition_method", "tchebycheff")

        if primary_algorithm == "milp":
            algorithm_config.milp_gap_tolerance = config.get("milp_gap_tolerance", 0.01)

        if primary_algorithm.startswith("hybrid"):
            algorithm_config.hybrid_milp_time_fraction = config.get("hybrid_milp_time_fraction", 0.3)
            if primary_algorithm == "hybrid_milp_nsga3":
                algorithm_config.reference_point_divisions = config.get("reference_point_divisions", 12)

        return algorithm_config

    def _select_best_algorithm(self, listings_df, user_wishlist_df, config) -> str:
        """
        Automatically select the best algorithm based on problem characteristics with NSGA-III support.

        Decision factors:
        - Problem size (number of cards and stores)
        - User preferences (strict vs flexible)
        - Time constraints
        - Complexity and diversity requirements
        """
        num_cards = len(user_wishlist_df)
        num_stores = listings_df["site_name"].nunique()
        total_listings = len(listings_df)

        # Calculate complexity metrics
        avg_stores_per_card = listings_df.groupby("name")["site_name"].nunique().mean()
        card_coverage = len(listings_df["name"].unique()) / num_cards

        # Get time limit from config
        time_limit = config.get("time_limit", 300) if isinstance(config, dict) else getattr(config, "time_limit", 300)

        # Calculate complexity score
        complexity_score = (num_cards * num_stores) / 1000
        
        logger.info(f"Algorithm selection metrics:")
        logger.info(f"  Cards: {num_cards}, Stores: {num_stores}")
        logger.info(f"  Avg stores per card: {avg_stores_per_card:.2f}")
        logger.info(f"  Card coverage: {card_coverage:.2%}")
        logger.info(f"  Time limit: {time_limit}s")
        logger.info(f"  Complexity score: {complexity_score:.3f}")

        # Decision rules with NSGA-III integration
        if num_cards <= 10 and num_stores <= 5:
            # Small problem - MILP is fast and optimal
            logger.info("Selected MILP: Small problem size")
            return "milp"

        elif num_cards <= 30 and avg_stores_per_card < 3:
            # Medium problem with limited options - MILP still good
            logger.info("Selected MILP: Medium size with limited options")
            return "milp"

        elif num_cards > 50 or num_stores > 20:
            # Large problem - evolutionary algorithms scale better
            if card_coverage < 0.8:
                # Poor coverage - MOEA/D handles constraints better
                logger.info("Selected MOEA/D: Large problem with poor coverage")
                return "moead"
            elif num_cards > 100 or (num_stores > 30 and avg_stores_per_card > 5):
                # Very large/complex problem - NSGA-III for enhanced diversity
                logger.info("Selected NSGA-III: Very large problem requiring enhanced diversity")
                return "nsga3"
            else:
                # Good coverage - NSGA-II for speed
                logger.info("Selected NSGA-II: Large problem with good coverage")
                return "nsga2"

        elif time_limit < 60:
            # Tight time constraint - use faster algorithm
            logger.info("Selected NSGA-II: Tight time constraint")
            return "nsga2"

        else:
            # Default to hybrid for best of both worlds
            # Choose hybrid type based on problem characteristics
            if num_cards > 75 or (num_stores > 25 and card_coverage > 0.9):
                logger.info("Selected Hybrid MILP+NSGA-III: Large problem with good coverage requiring diversity")
                return "hybrid_milp_nsga3"
            else:
                logger.info("Selected Hybrid MILP+MOEA/D: Default choice for balanced performance")
                return "hybrid_milp_moead"

    def _analyze_problem_characteristics(self, listings_df, user_wishlist_df) -> Dict:
        """Analyze problem characteristics for metrics and algorithm selection with diversity factors"""
        characteristics = {
            "num_cards": len(user_wishlist_df),
            "num_stores": listings_df["site_name"].nunique(),
            "total_listings": len(listings_df),
            "avg_stores_per_card": listings_df.groupby("name")["site_name"].nunique().mean(),
            "card_coverage": len(listings_df["name"].unique()) / len(user_wishlist_df),
            "price_variance": listings_df.groupby("name")["price"].std().mean(),
            "quality_distribution": listings_df["quality"].value_counts().to_dict(),
        }

        # Enhanced complexity score with diversity factors
        complexity_factors = [
            min(characteristics["num_cards"] / 100, 1),  # Card count factor
            min(characteristics["num_stores"] / 30, 1),  # Store count factor
            1 - characteristics["card_coverage"],  # Coverage factor
            min(characteristics["price_variance"] / 50, 1),  # Price variance factor
        ]
        
        # Add diversity requirement factor
        diversity_requirement = 0.0
        if characteristics["num_cards"] > 50 and characteristics["num_stores"] > 15:
            diversity_requirement = min((characteristics["num_cards"] * characteristics["num_stores"]) / 2000, 1)
        
        complexity_factors.append(diversity_requirement)
        characteristics["complexity_score"] = sum(complexity_factors) / len(complexity_factors)
        characteristics["diversity_requirement"] = diversity_requirement

        # Recommendation for NSGA-III
        characteristics["nsga3_recommended"] = (
            characteristics["complexity_score"] > 0.7 and 
            characteristics["diversity_requirement"] > 0.5
        )

        return characteristics

    async def _run_optimization_async(self, optimizer):
        """Run optimization in async context"""
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, optimizer.optimize)

    def _setup_progress_tracking(self, optimizer, task_updater):
        """Set up progress tracking callbacks for the optimizer"""

        def update_progress(progress: float, message: str):
            if task_updater:
                # Map optimizer progress (0-1) to celery task progress (60-100)
                task_progress = 60 + (progress * 40)
                
                # Add algorithm-specific information
                algo_info = {
                    "algorithm": optimizer.get_algorithm_name(),
                }
                
                # Add NSGA-III specific info if applicable
                if hasattr(optimizer, 'ref_points') and optimizer.ref_points is not None:
                    algo_info["reference_points"] = len(optimizer.ref_points)
                
                task_updater.update_state(
                    state="PROCESSING",
                    meta={
                        "status": message,
                        "progress": int(task_progress),
                        **algo_info,
                    },
                )

        # Attach callback to optimizer if supported
        if hasattr(optimizer, "set_progress_callback"):
            optimizer.set_progress_callback(update_progress)

    def _calculate_solution_quality(self, result) -> float:
        """
        Calculate a quality score for the solution (0-1) with diversity consideration.

        Factors:
        - Completeness (cards found vs requested)
        - Cost efficiency
        - Store count efficiency
        - Solution diversity (for multi-objective algorithms)
        """
        if not result.best_solution:
            return 0.0

        solution = result.best_solution

        # Completeness score
        cards_requested = solution.get("cards_required_total", 1)
        cards_found = solution.get("nbr_card_in_solution", 0)
        completeness_score = cards_found / cards_requested if cards_requested > 0 else 0

        # Cost efficiency (compared to average)
        # This is simplified - in practice, you'd want to compare to market average
        cost_efficiency_score = 1.0  # Placeholder

        # Store efficiency (fewer stores is better)
        max_stores = 10  # Assume 10 is the practical maximum
        store_count = solution.get("number_store", max_stores)
        store_efficiency_score = 1 - (store_count / max_stores)

        # Diversity bonus for NSGA-III and multi-objective algorithms
        diversity_bonus = 0.0
        if result.algorithm_used and "nsga" in result.algorithm_used.lower():
            # Check if multiple solutions were found (indicator of diversity)
            if hasattr(result, "all_solutions") and len(result.all_solutions or []) > 5:
                diversity_bonus = 0.1  # 10% bonus for diverse solution sets

        # Weighted average with diversity consideration
        quality_score = (
            0.5 * completeness_score + 
            0.3 * cost_efficiency_score + 
            0.2 * store_efficiency_score + 
            diversity_bonus
        )

        return min(max(quality_score, 0.0), 1.0)

    def _format_for_existing_system(self, result):
        """Convert OptimizationResult to format expected by existing system"""
        return {
            "status": "success" if result.best_solution else "failed",
            "best_solution": result.best_solution,
            "iterations": result.all_solutions,
            "algorithm_used": result.algorithm_used,
            "execution_time": result.execution_time,
            "type": result.algorithm_used.lower().replace("-", "_"),
            "performance_stats": result.performance_stats,
            "errors": self._extract_errors_from_result(result),
        }

    def _extract_errors_from_result(self, result) -> Dict[str, List[str]]:
        """Extract errors from optimization result"""
        if hasattr(result, "errors") and result.errors:
            return result.errors

        # Try to get from ErrorCollector if available
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

    def _generate_cache_key(self, user_wishlist_df, config) -> str:
        """Generate a deterministic cache key for the optimization request"""
        import hashlib, json

        # Sort wishlist JSON for consistent key ordering
        wishlist_str = json.dumps(json.loads(user_wishlist_df.to_json(orient="records")), sort_keys=True)

        # Convert config to dict if needed
        if hasattr(config, "to_dict"):
            config_dict = config.to_dict()
        else:
            config_dict = config

        # Extract and sort relevant config params
        config_relevant = {k: config_dict.get(k) for k in ["min_store", "max_store", "strict_preferences"]}
        config_str = json.dumps(config_relevant, sort_keys=True)

        cache_string = f"{wishlist_str}_{config_str}"
        return hashlib.md5(cache_string.encode()).hexdigest()

    def _add_to_cache(self, key: str, result: Dict):
        """Add result to cache with size limit"""
        if len(self._result_cache) >= self._cache_max_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._result_cache))
            del self._result_cache[oldest_key]

        self._result_cache[key] = result

    def _log_optimization_summary(self, result, characteristics: Dict):
        """Log a summary of the optimization results with NSGA-III insights"""
        logger.info("=" * 60)
        logger.info("OPTIMIZATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Algorithm: {result.algorithm_used}")
        logger.info(f"Execution Time: {result.execution_time:.2f} seconds")
        logger.info(f"Problem Complexity: {characteristics['complexity_score']:.2f}")
        
        # NSGA-III specific logging
        if "nsga3" in result.algorithm_used.lower() or "nsga-iii" in result.algorithm_used.lower():
            logger.info(f"Diversity Requirement: {characteristics.get('diversity_requirement', 0):.2f}")
            if result.performance_stats and "reference_points_used" in result.performance_stats:
                logger.info(f"Reference Points Used: {result.performance_stats['reference_points_used']}")
            if result.performance_stats and "diversity_metric" in result.performance_stats:
                logger.info(f"Solution Diversity: {result.performance_stats['diversity_metric']:.3f}")

        if result.best_solution:
            solution = result.best_solution
            logger.info(f"Cards Found: {solution.get('nbr_card_in_solution', 0)}/{characteristics['num_cards']}")
            logger.info(f"Total Cost: ${solution.get('total_price', 0):.2f}")
            logger.info(f"Stores Used: {solution.get('number_store', 0)}")
            logger.info(f"Solution Quality: {self._calculate_solution_quality(result):.2%}")

            # Log performance stats if available
            if result.performance_stats:
                logger.info("Performance Stats:")
                for key, value in result.performance_stats.items():
                    logger.info(f"  {key}: {value}")
        else:
            logger.info("No solution found")

        logger.info("=" * 60)

    def get_algorithm_statistics(self) -> Dict[str, Any]:
        """Get performance statistics for all algorithms including NSGA-III"""
        stats = {}
        # "last_5_runs": self.metrics_tracker.get_recent_runs(algorithm, limit=5)
        for algorithm in self.optimizer_factory.get_available_algorithms():
            perf = self.metrics_tracker.get_algorithm_performance(algorithm)
            if perf:
                stats[algorithm] = perf
        return stats

    def clear_cache(self):
        """Clear the result cache"""
        self._result_cache.clear()
        logger.info("Optimization result cache cleared")