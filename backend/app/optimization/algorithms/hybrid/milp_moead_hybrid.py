# backend/app/optimization/algorithms/hybrid/milp_moead_hybrid.py
from typing import Dict, List, Optional
import logging
import time
from ...core.base_optimizer import BaseOptimizer, OptimizationResult
from ..milp.milp_optimizer import MILPOptimizer
from ..evolutionary.moead_optimizer import MOEADOptimizer
from ..evolutionary.nsga2_optimizer import NSGA2Optimizer

logger = logging.getLogger(__name__)


class HybridMILPMOEADOptimizer(BaseOptimizer):
    """
    Hybrid MILP + MOEA/D optimizer with three-phase strategy:
    1. Quick MILP for feasibility and initial solution
    2. MOEA/D (or NSGA-II fallback) with MILP seeding
    3. Local search refinement
    """

    def __init__(self, problem_data: Dict, config: Dict):
        super().__init__(problem_data, config)
        self.filtered_listings_df = problem_data["filtered_listings_df"]
        self.user_wishlist_df = problem_data["user_wishlist_df"]

        # Determine which evolutionary algorithm to use
        self.use_moead = config.get("use_moead", True)
        self.evolutionary_algorithm = "MOEA/D" if self.use_moead else "NSGA-II"

        # Phase timing configuration
        self.milp_time_limit = config.get("milp_time_limit", 30)  # seconds
        self.evolutionary_time_limit = config.get("evolutionary_time_limit", 60)
        self.local_search_time_limit = config.get("local_search_time_limit", 20)

    def optimize(self) -> OptimizationResult:
        """Hybrid optimization strategy with consistent result handling"""
        self._start_timing()

        try:
            # Phase 1: Quick MILP for feasibility and seeding
            logger.info("Phase 1: Running quick MILP optimization for feasibility")
            milp_start = time.time()

            # Configure MILP for quick solution
            milp_config = self.config.copy()
            milp_config["time_limit"] = self.milp_time_limit
            milp_config["find_min_store"] = True  # Focus on finding feasible solution quickly

            milp_optimizer = MILPOptimizer(self.problem_data, milp_config)
            milp_optimizer.set_progress_callback(self._update_progress)
            milp_result = milp_optimizer.optimize()

            milp_time = time.time() - milp_start
            logger.info(f"MILP completed in {milp_time:.2f} seconds")

            # Check if MILP found a complete solution with consistent field access
            milp_solution = None
            if milp_result.best_solution:
                # Use helper function to get missing cards count
                missing_count = 0
                if "missing_cards_count" in milp_result.best_solution:
                    missing_count = milp_result.best_solution["missing_cards_count"]
                elif "missing_cards" in milp_result.best_solution:
                    missing_count = len(milp_result.best_solution["missing_cards"])

                if missing_count == 0:
                    milp_solution = milp_result.best_solution
                    price = milp_solution.get("total_price", 0)
                    logger.info(f"MILP found complete solution with cost ${price:.2f}")
                else:
                    logger.warning(f"MILP found incomplete solution (missing {missing_count} cards)")
            else:
                logger.warning("MILP did not find any solution, proceeding without seeding")

            # Phase 2: Evolutionary algorithm with MILP seeding
            logger.info(f"Phase 2: Running {self.evolutionary_algorithm} optimization")
            evolutionary_start = time.time()

            # Configure evolutionary algorithm
            evolutionary_config = self.config.copy()
            evolutionary_config["max_generations"] = 100
            evolutionary_config["population_size"] = 200

            if self.use_moead:
                try:
                    evolutionary_optimizer = MOEADOptimizer(self.problem_data, evolutionary_config)
                    evolutionary_optimizer.set_progress_callback(self._update_progress)
                    if milp_solution:
                        # Seed MOEA/D with MILP solution
                        evolutionary_result = self._run_seeded_moead(
                            evolutionary_optimizer, milp_solution, evolutionary_config
                        )
                    else:
                        evolutionary_result = evolutionary_optimizer.optimize()
                except Exception as e:
                    logger.warning(f"MOEA/D failed: {str(e)}, falling back to NSGA-II")
                    self.use_moead = False
                    self.evolutionary_algorithm = "NSGA-II"

            if not self.use_moead:
                # Use NSGA-II as fallback
                evolutionary_optimizer = NSGA2Optimizer(self.problem_data, evolutionary_config)
                evolutionary_optimizer.set_progress_callback(self._update_progress)
                if milp_solution:
                    evolutionary_result = self._run_seeded_nsga2(
                        evolutionary_optimizer, milp_solution, evolutionary_config
                    )
                else:
                    evolutionary_result = evolutionary_optimizer.optimize()

            evolutionary_time = time.time() - evolutionary_start
            logger.info(f"{self.evolutionary_algorithm} completed in {evolutionary_time:.2f} seconds")

            # Phase 3: Local search refinement
            logger.info("Phase 3: Local search refinement")
            local_search_start = time.time()

            # Select best solution for refinement
            best_solution = self._select_best_solution(milp_result, evolutionary_result)

            if best_solution:
                refined_solution = self._local_search_refinement(best_solution, time_limit=self.local_search_time_limit)

                local_search_time = time.time() - local_search_start
                logger.info(f"Local search completed in {local_search_time:.2f} seconds")

                # Combine all solutions from different phases
                all_solutions = []
                if milp_result.all_solutions:
                    all_solutions.extend(milp_result.all_solutions[:5])  # Top 5 MILP solutions
                if evolutionary_result.all_solutions:
                    all_solutions.extend(evolutionary_result.all_solutions[:10])  # Top 10 evolutionary
                if refined_solution != best_solution:
                    all_solutions.insert(0, refined_solution)  # Add refined if different

                self._end_timing()

                return OptimizationResult(
                    best_solution=refined_solution,
                    all_solutions=all_solutions,
                    algorithm_used=f"Hybrid-MILP-{self.evolutionary_algorithm}",
                    execution_time=self.get_execution_time(),
                    iterations=len(all_solutions),
                    convergence_metric=0.0,
                    performance_stats={
                        **self.execution_stats,
                        "milp_time": milp_time,
                        "evolutionary_time": evolutionary_time,
                        "local_search_time": local_search_time,
                        "phases_completed": 3,
                    },
                )
            else:
                # No good solution found
                self._end_timing()
                return self._create_failed_result()

        except Exception as e:
            logger.error(f"Hybrid optimization failed: {str(e)}")
            self._end_timing()
            return self._create_failed_result()

    def _run_seeded_moead(self, optimizer: MOEADOptimizer, seed_solution: Dict, config: Dict):
        """Run MOEA/D with MILP solution as seed"""
        # Convert MILP solution to population seed
        # This is a simplified version - in practice, you'd want to properly convert
        # the solution format and create variations
        logger.info("Seeding MOEA/D with MILP solution")

        # For now, just run standard MOEA/D
        # TODO: Implement proper seeding mechanism
        return optimizer.optimize()

    def _run_seeded_nsga2(self, optimizer: NSGA2Optimizer, seed_solution: Dict, config: Dict):
        """Run NSGA-II with MILP solution as seed"""
        # The NSGA-II optimizer already has support for MILP seeding
        # We need to extract the solution in the right format
        if "stores" in seed_solution:
            # Extract card list from standardized format
            milp_cards = []
            for store in seed_solution["stores"]:
                milp_cards.extend(store["cards"])

            # Create a modified optimize method that accepts seed
            return self._run_nsga2_with_seed(optimizer, milp_cards)
        else:
            return optimizer.optimize()

    def _run_nsga2_with_seed(self, optimizer: NSGA2Optimizer, seed_cards: List[Dict]):
        """Helper to run NSGA-II with seed solution"""
        # This would require modifying the NSGA2 optimizer to accept a seed
        # For now, just run standard optimization
        return optimizer.optimize()

    def _select_best_solution(self, milp_result: OptimizationResult, evolutionary_result: OptimizationResult) -> Dict:
        """Select the best solution from both algorithms with consistent field access"""
        solutions = []

        if milp_result.best_solution:
            solutions.append(("MILP", milp_result.best_solution))

        if evolutionary_result.best_solution:
            solutions.append((self.evolutionary_algorithm, evolutionary_result.best_solution))

        if not solutions:
            return None

        def get_missing_cards_count(solution: Dict) -> int:
            """Get missing cards count with fallback to different field names"""
            # Try new field name first
            if "missing_cards_count" in solution:
                return solution["missing_cards_count"]
            # Fallback to legacy field names
            elif "missing_cards" in solution:
                return len(solution["missing_cards"])
            # Calculate from completeness if available
            elif "cards_required_total" in solution and "cards_found_total" in solution:
                return max(0, solution["cards_required_total"] - solution["cards_found_total"])
            # Last resort
            else:
                return float("inf")

        def get_total_price(solution: Dict) -> float:
            """Get total price with consistent field access"""
            return solution.get("total_price", float("inf"))

        def get_completeness_score(solution: Dict) -> float:
            """Get completeness score for solution ranking"""
            # Try new completeness field first
            if "completeness_by_quantity" in solution:
                return solution["completeness_by_quantity"]
            # Calculate from card counts
            elif "cards_required_total" in solution and "cards_found_total" in solution:
                required = solution["cards_required_total"]
                found = solution["cards_found_total"]
                return found / required if required > 0 else 0.0
            # Legacy calculation
            elif "missing_cards_count" in solution and "cards_required_total" in solution:
                missing = solution["missing_cards_count"]
                required = solution["cards_required_total"]
                return max(0.0, (required - missing) / required) if required > 0 else 0.0
            else:
                return 0.0

        # IMPROVED SELECTION: Sort by completeness first, then cost
        def solution_key(algo_solution_tuple):
            algo, solution = algo_solution_tuple
            completeness = get_completeness_score(solution)
            missing_count = get_missing_cards_count(solution)
            total_price = get_total_price(solution)

            # Primary: prefer complete solutions (completeness >= 1.0)
            # Secondary: minimize missing cards
            # Tertiary: minimize cost
            return (-completeness, missing_count, total_price)

        best_algo, best_solution = min(solutions, key=solution_key)

        # CLEAR LOGGING: Use consistent field access for logging
        completeness = get_completeness_score(best_solution)
        missing_count = get_missing_cards_count(best_solution)
        total_price = get_total_price(best_solution)

        logger.info(f"Selected {best_algo} solution as best:")
        logger.info(f"  Cost: ${total_price:.2f}")
        logger.info(f"  Completeness: {completeness:.1%}")
        logger.info(f"  Missing cards: {missing_count}")

        return best_solution

    def _local_search_refinement(self, solution: Dict, time_limit: int = 20) -> Dict:
        """
        Apply local search refinement with consistent field access

        Strategies:
        1. Store consolidation - try to reduce number of stores
        2. Price improvement - find cheaper alternatives within same stores
        3. Quality upgrade - upgrade quality if price difference is minimal
        """
        logger.info("Starting local search refinement")
        start_time = time.time()

        improved_solution = solution.copy()
        improvements_made = 0

        def get_store_count(sol: Dict) -> int:
            """Get store count with consistent field access"""
            if "number_store" in sol:
                return sol["number_store"]
            elif "stores" in sol:
                return len(sol["stores"])
            else:
                return 0

        def get_total_price(sol: Dict) -> float:
            """Get total price with consistent field access"""
            return sol.get("total_price", 0.0)

        # Strategy 1: Store consolidation
        if time.time() - start_time < time_limit:
            consolidated = self._try_store_consolidation(improved_solution)
            if consolidated:
                original_price = get_total_price(improved_solution)
                consolidated_price = get_total_price(consolidated)
                original_stores = get_store_count(improved_solution)
                consolidated_stores = get_store_count(consolidated)

                # Accept if price increase is <= 5% and store count decreased
                if consolidated_price <= original_price * 1.05 and consolidated_stores < original_stores:
                    improved_solution = consolidated
                    improvements_made += 1
                    logger.info(
                        f"Store consolidation: {original_stores} -> {consolidated_stores} stores, "
                        f"${original_price:.2f} -> ${consolidated_price:.2f}"
                    )

        # Strategy 2: Price improvement within stores
        if time.time() - start_time < time_limit:
            price_improved = self._try_price_improvement(improved_solution)
            if price_improved:
                original_price = get_total_price(improved_solution)
                improved_price = get_total_price(price_improved)

                if improved_price < original_price:
                    improved_solution = price_improved
                    improvements_made += 1
                    logger.info(f"Price improvement: ${original_price:.2f} -> ${improved_price:.2f}")

        # Strategy 3: Quality upgrade for minimal cost
        if time.time() - start_time < time_limit:
            quality_improved = self._try_quality_upgrade(improved_solution)
            if quality_improved:
                improved_solution = quality_improved
                improvements_made += 1
                logger.info("Quality upgrades applied where cost-effective")

        elapsed_time = time.time() - start_time
        logger.info(f"Local search completed in {elapsed_time:.2f}s with {improvements_made} improvements")

        return improved_solution

    def _try_store_consolidation(self, solution: Dict) -> Optional[Dict]:
        """Try to reduce the number of stores while maintaining cost efficiency"""
        # This is a placeholder - implement actual store consolidation logic
        return None

    def _try_price_improvement(self, solution: Dict) -> Optional[Dict]:
        """Find cheaper alternatives within the same stores"""
        # This is a placeholder - implement actual price improvement logic
        return None

    def _try_quality_upgrade(self, solution: Dict) -> Optional[Dict]:
        """Upgrade card quality where the price difference is minimal"""
        # This is a placeholder - implement actual quality upgrade logic
        return None

    def _create_failed_result(self) -> OptimizationResult:
        """Create a failed optimization result"""
        return OptimizationResult(
            best_solution={},
            all_solutions=[],
            algorithm_used=f"Hybrid-MILP-{self.evolutionary_algorithm}",
            execution_time=self.get_execution_time(),
            iterations=0,
            convergence_metric=1.0,
            performance_stats=self.execution_stats,
        )

    def get_algorithm_name(self) -> str:
        return f"Hybrid-MILP-{self.evolutionary_algorithm}"
