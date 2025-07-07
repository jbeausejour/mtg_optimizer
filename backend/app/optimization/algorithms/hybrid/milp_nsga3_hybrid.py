# backend/app/optimization/algorithms/hybrid/milp_nsga3_hybrid.py
from typing import Dict, List, Optional
import logging
import time
from ...core.base_optimizer import BaseOptimizer, OptimizationResult
from ..milp.milp_optimizer import MILPOptimizer
from ..evolutionary.nsga3_optimizer import NSGA3Optimizer

logger = logging.getLogger(__name__)


class HybridMILPNSGA3Optimizer(BaseOptimizer):
    """
    Hybrid MILP + NSGA-III optimizer optimized for large, complex problems:
    1. Quick MILP for feasibility and initial solution
    2. NSGA-III with reference point diversity and MILP seeding
    3. Local search refinement
    
    This hybrid is particularly good for:
    - Large problem instances (>50 cards, >20 stores)
    - When solution diversity is important
    - Complex multi-objective optimization scenarios
    """

    def __init__(self, problem_data: Dict, config: Dict):
        super().__init__(problem_data, config)
        self.filtered_listings_df = problem_data["filtered_listings_df"]
        self.user_wishlist_df = problem_data["user_wishlist_df"]

        # Phase timing configuration - optimized for NSGA-III
        self.milp_time_limit = config.get("milp_time_limit", 30)  # seconds
        self.nsga3_time_limit = config.get("nsga3_time_limit", 90)  # More time for reference point optimization
        self.local_search_time_limit = config.get("local_search_time_limit", 30)

        # NSGA-III specific configuration
        self.reference_point_divisions = config.get("reference_point_divisions", 12)
        self.population_size = config.get("population_size", 300)  # Larger for NSGA-III

    def optimize(self) -> OptimizationResult:
        """Hybrid optimization strategy with NSGA-III focus"""
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
            milp_optimizer.set_progress_callback(self._create_phase_progress_callback("MILP", 0, 30))
            milp_result = milp_optimizer.optimize()

            milp_time = time.time() - milp_start
            logger.info(f"MILP completed in {milp_time:.2f} seconds")

            # Check if MILP found a complete solution
            milp_solution = None
            if milp_result.best_solution:
                missing_count = self._get_missing_cards_count(milp_result.best_solution)
                if missing_count == 0:
                    milp_solution = milp_result.best_solution
                    price = milp_solution.get("total_price", 0)
                    logger.info(f"MILP found complete solution with cost ${price:.2f}")
                else:
                    logger.warning(f"MILP found incomplete solution (missing {missing_count} cards)")
            else:
                logger.warning("MILP did not find any solution, proceeding without seeding")

            # Phase 2: NSGA-III with reference point optimization
            logger.info("Phase 2: Running NSGA-III optimization with reference point diversity")
            nsga3_start = time.time()

            # Configure NSGA-III for enhanced diversity
            nsga3_config = self.config.copy()
            nsga3_config["time_limit"] = self.nsga3_time_limit
            nsga3_config["max_generations"] = 100
            nsga3_config["population_size"] = self.population_size
            nsga3_config["reference_point_divisions"] = self.reference_point_divisions

            nsga3_optimizer = NSGA3Optimizer(self.problem_data, nsga3_config)
            nsga3_optimizer.set_progress_callback(self._create_phase_progress_callback("NSGA-III", 30, 80))

            if milp_solution:
                # Seed NSGA-III with MILP solution for better initial population
                nsga3_result = self._run_seeded_nsga3(nsga3_optimizer, milp_solution, nsga3_config)
            else:
                nsga3_result = nsga3_optimizer.optimize()

            nsga3_time = time.time() - nsga3_start
            logger.info(f"NSGA-III completed in {nsga3_time:.2f} seconds")

            # Phase 3: Local search refinement
            logger.info("Phase 3: Local search refinement with diversity preservation")
            local_search_start = time.time()

            # Select best solution for refinement
            best_solution = self._select_best_solution(milp_result, nsga3_result)

            if best_solution:
                refined_solution = self._local_search_refinement(best_solution, time_limit=self.local_search_time_limit)

                local_search_time = time.time() - local_search_start
                logger.info(f"Local search completed in {local_search_time:.2f} seconds")

                # Combine all solutions with emphasis on diversity
                all_solutions = self._combine_diverse_solutions(milp_result, nsga3_result, refined_solution)

                self._end_timing()

                return OptimizationResult(
                    best_solution=refined_solution,
                    all_solutions=all_solutions,
                    algorithm_used="Hybrid-MILP-NSGA-III",
                    execution_time=self.get_execution_time(),
                    iterations=len(all_solutions),
                    convergence_metric=0.0,
                    performance_stats={
                        **self.execution_stats,
                        "milp_time": milp_time,
                        "nsga3_time": nsga3_time,
                        "local_search_time": local_search_time,
                        "phases_completed": 3,
                        "reference_points_used": len(nsga3_optimizer.ref_points) if hasattr(nsga3_optimizer, 'ref_points') else 0,
                        "diversity_metric": self._calculate_solution_diversity(all_solutions),
                    },
                )
            else:
                # No good solution found
                self._end_timing()
                return self._create_failed_result()

        except Exception as e:
            logger.error(f"Hybrid MILP+NSGA-III optimization failed: {str(e)}")
            self._end_timing()
            return self._create_failed_result()

    def _create_phase_progress_callback(self, phase_name: str, start_percent: int, end_percent: int):
        """Create progress callback for specific optimization phase"""
        def progress_callback(progress: float, message: str):
            # Map phase progress to overall progress
            phase_progress = start_percent + (progress * (end_percent - start_percent))
            full_message = f"{phase_name}: {message}"
            self._update_progress(phase_progress / 100.0, full_message)
        
        return progress_callback

    def _run_seeded_nsga3(self, optimizer: NSGA3Optimizer, seed_solution: Dict, config: Dict):
        """Run NSGA-III with MILP solution as seed"""
        logger.info("Seeding NSGA-III with MILP solution for enhanced initial population")

        # Extract card selection from MILP solution
        if "stores" in seed_solution:
            milp_cards = []
            for store in seed_solution["stores"]:
                milp_cards.extend(store["cards"])
            
            # Create variations of the MILP solution for population diversity
            # The NSGA-III optimizer would need to support this seeding mechanism
            logger.info(f"Creating population variations from {len(milp_cards)} MILP cards")
            
            # For now, run standard NSGA-III
            # TODO: Implement proper seeding mechanism in NSGA3Optimizer
            return optimizer.optimize()
        else:
            return optimizer.optimize()

    def _select_best_solution(self, milp_result: OptimizationResult, nsga3_result: OptimizationResult) -> Dict:
        """Select the best solution from both algorithms with NSGA-III considerations"""
        solutions = []

        if milp_result.best_solution:
            solutions.append(("MILP", milp_result.best_solution))

        if nsga3_result.best_solution:
            solutions.append(("NSGA-III", nsga3_result.best_solution))

        if not solutions:
            return None

        def solution_key(algo_solution_tuple):
            algo, solution = algo_solution_tuple
            completeness = self._get_completeness_score(solution)
            missing_count = self._get_missing_cards_count(solution)
            total_price = self._get_total_price(solution)

            # For NSGA-III hybrid, prioritize complete solutions strongly
            return (-completeness, missing_count, total_price)

        best_algo, best_solution = min(solutions, key=solution_key)

        # Log selection details
        completeness = self._get_completeness_score(best_solution)
        missing_count = self._get_missing_cards_count(best_solution)
        total_price = self._get_total_price(best_solution)

        logger.info(f"Selected {best_algo} solution as best:")
        logger.info(f"  Cost: ${total_price:.2f}")
        logger.info(f"  Completeness: {completeness:.1%}")
        logger.info(f"  Missing cards: {missing_count}")

        return best_solution

    def _combine_diverse_solutions(self, milp_result: OptimizationResult, nsga3_result: OptimizationResult, refined_solution: Dict) -> List[Dict]:
        """Combine solutions with emphasis on diversity from NSGA-III"""
        all_solutions = []

        # Add refined solution first
        if refined_solution:
            all_solutions.append(refined_solution)

        # Add NSGA-III solutions (they should already be diverse due to reference points)
        if nsga3_result.all_solutions:
            # Take more NSGA-III solutions since they're diverse
            all_solutions.extend(nsga3_result.all_solutions[:15])

        # Add top MILP solutions
        if milp_result.all_solutions:
            all_solutions.extend(milp_result.all_solutions[:5])

        # Remove duplicates while preserving diversity
        unique_solutions = self._remove_duplicate_solutions(all_solutions)
        
        logger.info(f"Combined {len(unique_solutions)} diverse solutions from all phases")
        return unique_solutions

    def _remove_duplicate_solutions(self, solutions: List[Dict]) -> List[Dict]:
        """Remove duplicate solutions while preserving diversity"""
        unique_solutions = []
        seen_signatures = set()

        for solution in solutions:
            # Create a signature based on key characteristics
            signature = (
                self._get_total_price(solution),
                self._get_missing_cards_count(solution),
                solution.get("number_store", 0)
            )
            
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_solutions.append(solution)

        return unique_solutions

    def _calculate_solution_diversity(self, solutions: List[Dict]) -> float:
        """Calculate diversity metric for solution set"""
        if len(solutions) < 2:
            return 0.0

        # Calculate diversity based on cost and store count variance
        costs = [self._get_total_price(sol) for sol in solutions]
        store_counts = [sol.get("number_store", 0) for sol in solutions]

        cost_variance = sum((c - sum(costs)/len(costs))**2 for c in costs) / len(costs) if costs else 0
        store_variance = sum((s - sum(store_counts)/len(store_counts))**2 for s in store_counts) / len(store_counts) if store_counts else 0

        # Normalize and combine
        diversity_score = min(1.0, (cost_variance + store_variance) / 1000)
        return diversity_score

    def _local_search_refinement(self, solution: Dict, time_limit: int = 30) -> Dict:
        """
        Apply local search refinement optimized for NSGA-III results
        
        Focus on:
        1. Reference point alignment - maintain solution characteristics
        2. Cost optimization without destroying diversity benefits
        3. Quality improvements where possible
        """
        logger.info("Starting NSGA-III-optimized local search refinement")
        start_time = time.time()

        improved_solution = solution.copy()
        improvements_made = 0

        # Strategy 1: Cost optimization while preserving solution structure
        if time.time() - start_time < time_limit / 3:
            cost_optimized = self._optimize_cost_structure(improved_solution)
            if cost_optimized and self._get_total_price(cost_optimized) < self._get_total_price(improved_solution):
                improved_solution = cost_optimized
                improvements_made += 1
                logger.info("Applied cost structure optimization")

        # Strategy 2: Quality improvements where cost-neutral
        if time.time() - start_time < time_limit * 2/3:
            quality_improved = self._improve_quality_cost_neutral(improved_solution)
            if quality_improved:
                improved_solution = quality_improved
                improvements_made += 1
                logger.info("Applied cost-neutral quality improvements")

        # Strategy 3: Store consolidation if beneficial
        if time.time() - start_time < time_limit:
            consolidated = self._try_beneficial_consolidation(improved_solution)
            if consolidated:
                improved_solution = consolidated
                improvements_made += 1
                logger.info("Applied beneficial store consolidation")

        elapsed_time = time.time() - start_time
        logger.info(f"NSGA-III local search completed in {elapsed_time:.2f}s with {improvements_made} improvements")

        return improved_solution

    def _optimize_cost_structure(self, solution: Dict) -> Optional[Dict]:
        """Optimize cost while preserving solution structure"""
        # Placeholder for cost structure optimization
        return None

    def _improve_quality_cost_neutral(self, solution: Dict) -> Optional[Dict]:
        """Improve quality where cost impact is neutral or minimal"""
        # Placeholder for quality improvement
        return None

    def _try_beneficial_consolidation(self, solution: Dict) -> Optional[Dict]:
        """Try store consolidation only if clearly beneficial"""
        # Placeholder for beneficial consolidation
        return None

    # Helper methods for consistent field access
    def _get_missing_cards_count(self, solution: Dict) -> int:
        """Get missing cards count with fallback to different field names"""
        if "missing_cards_count" in solution:
            return solution["missing_cards_count"]
        elif "missing_cards" in solution:
            return len(solution["missing_cards"])
        elif "cards_required_total" in solution and "cards_found_total" in solution:
            return max(0, solution["cards_required_total"] - solution["cards_found_total"])
        else:
            return float("inf")

    def _get_total_price(self, solution: Dict) -> float:
        """Get total price with consistent field access"""
        return solution.get("total_price", float("inf"))

    def _get_completeness_score(self, solution: Dict) -> float:
        """Get completeness score for solution ranking"""
        if "completeness_by_quantity" in solution:
            return solution["completeness_by_quantity"]
        elif "cards_required_total" in solution and "cards_found_total" in solution:
            required = solution["cards_required_total"]
            found = solution["cards_found_total"]
            return found / required if required > 0 else 0.0
        elif "missing_cards_count" in solution and "cards_required_total" in solution:
            missing = solution["missing_cards_count"]
            required = solution["cards_required_total"]
            return max(0.0, (required - missing) / required) if required > 0 else 0.0
        else:
            return 0.0

    def _create_failed_result(self) -> OptimizationResult:
        """Create a failed optimization result"""
        return OptimizationResult(
            best_solution={},
            all_solutions=[],
            algorithm_used="Hybrid-MILP-NSGA-III",
            execution_time=self.get_execution_time(),
            iterations=0,
            convergence_metric=1.0,
            performance_stats=self.execution_stats,
        )

    def get_algorithm_name(self) -> str:
        return "Hybrid-MILP-NSGA-III"