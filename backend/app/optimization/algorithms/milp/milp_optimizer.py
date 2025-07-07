# backend/app/optimization/algorithms/milp/milp_optimizer.py
from typing import Dict, List, Tuple, Any
import logging
import pandas as pd
import pulp
from pulp import PULP_CBC_CMD
from collections import defaultdict

from ...core.base_optimizer import BaseOptimizer, OptimizationResult
from ...preprocessing.penalty_calculator import PenaltyCalculator
from ...postprocessing.result_formatter import ResultFormatter
from app.constants import CardQuality

logger = logging.getLogger(__name__)


class MILPOptimizer(BaseOptimizer):
    """Enhanced MILP optimization algorithm using PuLP"""

    def __init__(self, problem_data: Dict, config: Dict):
        super().__init__(problem_data, config)

        # Extract data from problem_data
        self.filtered_listings_df = problem_data["filtered_listings_df"]
        self.user_wishlist_df = problem_data["user_wishlist_df"]

        # Initialize components
        self.penalty_calculator = PenaltyCalculator(config)
        self.result_formatter = ResultFormatter()
        self.result_formatter.set_filtered_listings_df(self.filtered_listings_df)

        # Create optimization config from dict
        self.optimization_config = self._create_optimization_config(config)

    def _create_optimization_config(self, config: Dict):
        """Create a mock optimization config object for backward compatibility"""

        class MockOptimizationConfig:
            def __init__(self, config_dict):
                self.weights = config_dict.get("weights", {"cost": 1.0, "quality": 1.0, "store_count": 0.3})
                self.min_store = config_dict.get("min_store", 1)
                self.max_store = config_dict.get("max_store", 10)
                self.find_min_store = config_dict.get("find_min_store", False)
                self.strict_preferences = config_dict.get("strict_preferences", False)
                self.high_cost = config_dict.get("high_cost", 10000.0)

        return MockOptimizationConfig(config)

    def optimize(self) -> OptimizationResult:
        """Run MILP optimization"""
        self._start_timing()
        self._update_progress(0.1, "Initializing MILP problem")

        try:
            # Setup optimization problem
            setup_results = self._setup_milp_problem()

            if any(result is None for result in setup_results):
                logger.error("Failed to setup MILP problem")
                return self._create_failed_result()

            filtered_df, unique_cards, unique_stores, costs_enriched = setup_results

            # Run optimization
            self._update_progress(0.7, "Solving MILP with PuLP")
            best_solution_df, all_iterations = self._solve_milp_problem(
                filtered_df, unique_cards, unique_stores, costs_enriched
            )

            self._end_timing()

            self._update_progress(1.0, "MILP optimization completed")
            if best_solution_df is not None:
                # Format solution using result formatter
                if isinstance(best_solution_df, pd.DataFrame):
                    solution_list = best_solution_df.to_dict("records")
                else:
                    solution_list = best_solution_df

                standardized_solution = self.result_formatter.format_solution(solution_list, self.user_wishlist_df)

                # Format all iterations
                formatted_iterations = []
                if all_iterations:
                    for iteration in all_iterations:
                        formatted_iterations.append(iteration)

                return OptimizationResult(
                    best_solution=standardized_solution,
                    all_solutions=formatted_iterations,
                    algorithm_used="MILP",
                    execution_time=self.get_execution_time(),
                    iterations=len(formatted_iterations),
                    convergence_metric=0.0,
                    performance_stats=self.execution_stats,
                )
            else:
                return self._create_failed_result()

        except Exception as e:
            logger.error(f"MILP optimization failed: {str(e)}")
            self._end_timing()
            return self._create_failed_result()

    def _setup_milp_problem(self) -> Tuple:
        """Setup the MILP optimization problem with data validation and preprocessing."""
        try:
            if self.user_wishlist_df is None or self.user_wishlist_df.empty:
                logger.error("user_wishlist_df is None or empty")
                return None, None, None, None, None

            if self.filtered_listings_df is None or self.filtered_listings_df.empty:
                logger.error("filtered_listings_df is None or empty")
                return None, None, None, None, None

            # Prepare dataframe
            filtered_df = self.filtered_listings_df.copy()
            filtered_df["site_name"] = filtered_df["site_name"].astype(str)
            filtered_df = filtered_df.loc[:, ~filtered_df.columns.duplicated()]

            unique_cards = self.user_wishlist_df["name"].unique()
            unique_stores = filtered_df["site_name"].unique()

            # Create card preferences from wishlist
            card_preferences = {
                row["name"]: {
                    "language": row.get("language", "English"),
                    "quality": row.get("quality", "NM"),
                    "version": row.get("version", "Standard"),
                    "set_name": row.get("set_name", ""),
                    "foil": row.get("foil", False),
                }
                for _, row in self.user_wishlist_df.iterrows()
            }

            # Apply penalties using the penalty calculator
            filtered_df = self.penalty_calculator.apply_penalties(
                filtered_df, card_preferences, self.optimization_config.strict_preferences
            )

            # Create enriched cost matrix
            enriched_costs = self._create_enriched_costs(filtered_df, unique_cards, unique_stores)

            return filtered_df, unique_cards, unique_stores, enriched_costs

        except Exception as e:
            logger.error(f"Error in _setup_milp_problem: {str(e)}", exc_info=True)
            return None, None, None, None, None

    def _create_enriched_costs(
        self, filtered_df: pd.DataFrame, unique_cards: List[str], unique_stores: List[str]
    ) -> Dict:
        """Create enriched cost matrix with additional card information"""
        enriched_costs = defaultdict(dict)

        for card in unique_cards:
            for store in unique_stores:
                rows = filtered_df[(filtered_df["name"] == card) & (filtered_df["site_name"] == store)]
                if rows.empty:
                    continue

                best = rows.sort_values("weighted_price").iloc[0]
                enriched = best.to_dict()
                enriched["weighted_price"] = best.get("weighted_price", best.get("price", 10000))
                enriched["available_quantity"] = best.get("quantity", 1.0)

                # Calculate quality score
                norm_quality = CardQuality.normalize(best.get("quality", "DMG"))
                max_q = max(CardQuality.get_weight(q.value) for q in CardQuality)
                enriched["quality_score"] = 1 - (CardQuality.get_weight(norm_quality) - 1) / (max_q - 1)

                enriched_costs[card][store] = enriched

        return enriched_costs

    def _solve_milp_problem(
        self,
        filtered_df: pd.DataFrame,
        unique_cards: List[str],
        unique_stores: List[str],
        enriched_costs: Dict,
    ):
        """Solve the MILP optimization problem with consistent card quantity tracking"""
        try:
            all_iterations_results = []
            best_solution = None

            # CLEAR NAMING: Calculate required cards from wishlist
            cards_required_total = int(self.user_wishlist_df["quantity"].sum())
            cards_required_unique = len(self.user_wishlist_df)

            logger.info("=" * 50)
            logger.info(f"Cards required (total quantity): {cards_required_total}")
            logger.info(f"Cards required (unique types): {cards_required_unique}")
            logger.info(f"Available stores: {len(unique_stores)}")

            strategy_msg = (
                "Minimize store count"
                if self.optimization_config.find_min_store
                else f"Minimum {self.optimization_config.min_store} stores"
            )
            logger.info(f"Strategy: {strategy_msg}")

            # Evaluation function for different strategies
            def evaluate_solution(store_count, zero_weights=False):
                weights = (self.optimization_config.weights or {}).copy()
                if zero_weights:
                    weights = {k: 0.0 for k in weights}

                filtered = filtered_df.copy()
                if zero_weights:
                    filtered["weighted_price"] = filtered["price"]

                prob, buy_vars, total_possible_cost = self._setup_pulp_problem(
                    enriched_costs, unique_cards, unique_stores, store_count, weights
                )

                if pulp.LpStatus[prob.status] != "Optimal":
                    logger.info(f"No feasible solution found with {store_count} store(s)")
                    return None

                # FIXED: Pass required card counts to processing
                result = self._process_milp_result(
                    buy_vars, enriched_costs, filtered, cards_required_total, cards_required_unique
                )

                # Calculate normalized metrics
                normalized_cost = result.get("total_price", 0) / total_possible_cost
                normalized_store_count = result.get("number_store", 0) / len(unique_stores)
                normalized_quality = result.get("normalized_quality", 0)

                weighted_score = (
                    weights.get("cost", 0.0) * normalized_cost
                    + weights.get("store_count", 0.0) * normalized_store_count
                    + weights.get("quality", 0.0) * normalized_quality
                )
                result["weighted_score"] = round(weighted_score, 6)

                # CLEAR LOGGING: Use consistent terminology
                if result["cards_found_total"] < cards_required_total:
                    missing_count = cards_required_total - result["cards_found_total"]
                    logger.warning(
                        f"[MILP][{store_count} stores] Incomplete solution: "
                        f"{result['cards_found_total']}/{cards_required_total} cards, "
                        f"missing {missing_count} cards"
                    )
                else:
                    logger.info(
                        f"[MILP][{store_count} stores] Complete solution: "
                        f"{len(result['stores'])} stores, cost ${result['total_price']:.2f}"
                    )

                all_iterations_results.append(result)
                return result

            # Strategy 1: Minimize store count
            if self.optimization_config.find_min_store:
                logger.info("Starting optimization to find minimum stores needed")

                complete_solutions = []
                best_store_count = None

                for store_count in range(1, len(unique_stores) + 1):
                    logger.info(f"[Feasibility] Trying solution with {store_count} store(s)")

                    result = evaluate_solution(store_count, zero_weights=True)
                    if not result:
                        continue

                    # FIXED: Use consistent field name for completeness check
                    if result.get("cards_found_total") == cards_required_total:
                        complete_solutions.append(result)
                        if best_store_count is None:
                            best_store_count = store_count

                        if len(complete_solutions) > 1:
                            prev = complete_solutions[-2]["total_price"]
                            curr = complete_solutions[-1]["total_price"]
                            if (prev - curr) < (curr * 0.1):
                                logger.info("Stopping search — minimal cost improvement")
                                break

                if not complete_solutions:
                    logger.warning("No complete solution found during store count minimization")
                    return None, all_iterations_results

                # Re-optimize with weights
                logger.info(f"Re-optimizing with weights at best store count = {best_store_count}")
                weighted_result = evaluate_solution(best_store_count, zero_weights=False)

                if weighted_result and weighted_result["cards_found_total"] == cards_required_total:
                    best_solution = weighted_result
                else:
                    best_price = min(sol["total_price"] for sol in complete_solutions)
                    near_best = [sol for sol in complete_solutions if sol["total_price"] <= best_price * 1.05]
                    best_solution = (
                        min(near_best, key=lambda x: x["number_store"]) if near_best else complete_solutions[0]
                    )

            # Strategy 2: Optimize with fixed min_store
            else:
                result = evaluate_solution(self.optimization_config.min_store)
                if result:
                    best_solution = result
                    logger.info(">>> Optimization with fixed min_store succeeded.")
                else:
                    logger.warning("No feasible solution with the minimum store constraint.")
                    return None, all_iterations_results

            if best_solution:
                return best_solution["sorted_results_df"], all_iterations_results
            else:
                return None, all_iterations_results

        except Exception as e:
            logger.error(f"Error in _solve_milp_problem: {str(e)}", exc_info=True)
            return None, None

    def _process_milp_result(
        self,
        buy_vars: Dict,
        costs: Dict,
        filtered_listings_df: pd.DataFrame,
        cards_required_total: int,
        cards_required_unique: int,
    ) -> Dict:
        """Process MILP solution with consistent card quantity tracking"""

        # CLEAR INITIALIZATION: Use descriptive names
        total_price = 0.0
        results = []
        cards_found_total = 0  # Total quantity of cards found
        cards_found_unique_names = set()  # Unique card names found
        store_usage = defaultdict(int)

        # Get all required card names for completeness checking
        all_required_card_names = set(card for card, _ in buy_vars.items())

        for card, store_dict in buy_vars.items():
            for store, var in store_dict.items():
                quantity = int(var.value() or 0)
                if quantity > 0:
                    try:
                        weighted_price = round(costs[card][store]["weighted_price"], 2)
                    except KeyError:
                        logger.error(f"[ERROR] No cost info for {card} at {store}")
                        continue

                    if weighted_price != 10000:  # Only include valid cards
                        # Find matching cards using weighted_price
                        matching_cards = filtered_listings_df[
                            (filtered_listings_df["name"] == card)
                            & (filtered_listings_df["site_name"] == store)
                            & (abs(filtered_listings_df["weighted_price"] - weighted_price) < 0.01)
                        ]

                        if matching_cards.empty:
                            # Try finding closest match
                            potential_matches = filtered_listings_df[
                                (filtered_listings_df["name"] == card) & (filtered_listings_df["site_name"] == store)
                            ]

                            if not potential_matches.empty:
                                closest_match_idx = (
                                    (potential_matches["weighted_price"] - weighted_price).abs().idxmin()
                                )
                                matching_cards = filtered_listings_df.loc[[closest_match_idx]]

                        if not matching_cards.empty:
                            card_data = matching_cards.iloc[0]
                            actual_price = float(card_data["price"])

                            # CLEAR TRACKING: Update all counters consistently
                            cards_found_unique_names.add(card)
                            total_price += quantity * actual_price
                            cards_found_total += quantity  # Only count once here
                            store_usage[store] += 1

                            results.append(
                                {
                                    "site_name": store,
                                    "site_id": card_data.get("site_id"),
                                    "name": card,
                                    "set_name": card_data["set_name"],
                                    "set_code": card_data["set_code"],
                                    "language": card_data.get("language", "English"),
                                    "version": card_data.get("version", "Standard"),
                                    "foil": bool(card_data.get("foil", False)),
                                    "quality": card_data["quality"],
                                    "quantity": int(quantity),
                                    "price": actual_price,
                                    "variant_id": card_data.get("variant_id"),
                                }
                            )

        # Create result structure
        results_df = pd.DataFrame(results)
        sorted_results_df = results_df.sort_values(by=["site_name", "name"]) if not results_df.empty else pd.DataFrame()
        sorted_results_df.reset_index(drop=True, inplace=True)

        # CLEAR COMPLETENESS CALCULATION
        missing_card_names = sorted(list(all_required_card_names - cards_found_unique_names))
        cards_found_unique = len(cards_found_unique_names)

        # Calculate completeness metrics
        completeness_by_quantity = cards_found_total / cards_required_total if cards_required_total > 0 else 0.0
        completeness_by_unique = cards_found_unique / cards_required_unique if cards_required_unique > 0 else 0.0

        # Group cards by store
        stores_data = defaultdict(list)
        for card in results:
            stores_data[card["site_name"]].append(card)

        stores = [
            {"site_name": store, "site_id": cards[0]["site_id"], "cards": cards} for store, cards in stores_data.items()
        ]

        # Add penalty information
        results = self.result_formatter.add_penalty_info_to_results(results, filtered_listings_df)

        store_usage_str = ", ".join(f"{store}: {count}" for store, count in store_usage.items())

        # CONSISTENT RESULT STRUCTURE: Clear field names and no duplicates
        return {
            # Card quantity metrics (no confusion)
            "cards_required_total": cards_required_total,
            "cards_required_unique": cards_required_unique,
            "cards_found_total": cards_found_total,
            "cards_found_unique": cards_found_unique,
            # Completeness metrics
            "completeness_by_quantity": completeness_by_quantity,
            "completeness_by_unique": completeness_by_unique,
            "is_complete": completeness_by_quantity >= 1.0,
            # Missing cards
            "missing_cards": missing_card_names,
            "missing_cards_count": len(missing_card_names),
            # Financial and store metrics
            "total_price": float(total_price),
            "number_store": len(stores),
            "list_stores": store_usage_str,
            "stores": stores,
            # Legacy compatibility (can be removed later)
            "nbr_card_in_solution": cards_found_total,  # Deprecated, use cards_found_total
            "total_card_found": cards_found_total,  # Deprecated, use cards_found_total
            # Data for further processing
            "sorted_results_df": sorted_results_df,
        }

    def _setup_pulp_problem(
        self,
        costs_enriched: Dict,
        unique_cards: List[str],
        unique_stores: List[str],
        store_count: int = None,
        weights: Dict = None,
    ):
        """Setup PuLP optimization problem"""
        prob = pulp.LpProblem("MTGCardOptimization", pulp.LpMinimize)

        if weights is None:
            weights = self.optimization_config.weights or {}

        # Decision variables
        buy_vars = {}
        for card in unique_cards:
            buy_vars[card] = {}
            for store in costs_enriched[card]:
                buy_vars[card][store] = pulp.LpVariable(f"Buy_{card}_{store}", 0, 1, pulp.LpBinary)

        store_vars = {}
        for store in unique_stores:
            store_vars[store] = pulp.LpVariable(f"Store_{store}", 0, 1, pulp.LpBinary)

        # Objective function
        objective_terms = []

        # Cost component
        total_possible_cost = sum(
            min(costs_enriched[card][store]["weighted_price"] for store in costs_enriched[card])
            for card in unique_cards
            if costs_enriched[card]
        )

        cost_weight = weights.get("cost", 1.0)
        if cost_weight > 0 and total_possible_cost > 0:
            normalized_cost_term = (
                pulp.lpSum(
                    buy_vars[card][store] * costs_enriched[card][store]["weighted_price"]
                    for card in unique_cards
                    for store in costs_enriched.get(card, {})
                )
                / total_possible_cost
            )
            objective_terms.append(cost_weight * normalized_cost_term)

        # Store count component
        store_weight = weights.get("store_count", 0.0)
        if store_weight > 0:
            normalized_store_term = pulp.lpSum(store_vars[store] for store in unique_stores) / len(unique_stores)
            objective_terms.append(store_weight * normalized_store_term)

        # Quality component
        quality_weight = weights.get("quality", 0.0)
        if quality_weight > 0:
            quality_penalties = []
            total_quality_slots = 0

            for card in unique_cards:
                for store in unique_stores:
                    listing = costs_enriched.get(card, {}).get(store)
                    if not listing:
                        continue

                    quality_score = listing.get("quality_score", 0)
                    q_penalty = 1 - quality_score
                    quality_penalties.append(q_penalty * buy_vars[card][store])
                    total_quality_slots += 1

            if total_quality_slots > 0:
                normalized_quality_term = 1 - (pulp.lpSum(quality_penalties) / total_quality_slots)
                objective_terms.append(quality_weight * normalized_quality_term)

        if objective_terms:
            prob += pulp.lpSum(objective_terms), "WeightedObjective"

        # Constraints
        # Quantity constraints
        for card in unique_cards:
            required_quantity = self.user_wishlist_df[self.user_wishlist_df["name"] == card]["quantity"].iloc[0]
            available_stores = list(costs_enriched.get(card, {}).keys())

            if available_stores:
                prob += (
                    pulp.lpSum([buy_vars[card][store] for store in available_stores]) == required_quantity,
                    f"Required_quantity_{card}",
                )

        # Store activation constraints
        M = len(unique_cards)
        for store in unique_stores:
            used_vars = [buy_vars[card][store] for card in unique_cards if store in costs_enriched.get(card, {})]

            if used_vars:
                prob += (
                    pulp.lpSum(used_vars) <= M * store_vars[store],
                    f"Store_usage_{store}",
                )
                prob += (
                    pulp.lpSum(used_vars) >= store_vars[store],
                    f"Store_usage_min_{store}",
                )

        # Store count constraints
        min_store = self.optimization_config.min_store
        max_store = self.optimization_config.max_store

        if len(unique_stores) < min_store:
            min_store = len(unique_stores)

        used_store_vars = [store_vars[store] for store in unique_stores]

        if self.optimization_config.find_min_store and store_count:
            prob += (pulp.lpSum(used_store_vars) >= min_store, "Min_stores")
            prob += (pulp.lpSum(used_store_vars) <= store_count, "Max_store_cap_for_find_min")
        else:
            prob += (pulp.lpSum(used_store_vars) >= min_store, "Min_stores_required")
            prob += (pulp.lpSum(used_store_vars) <= max_store, "Max_stores_allowed")

        # Solve
        solver = PULP_CBC_CMD(msg=False, threads=4, timeLimit=120, gapRel=0.01, presolve=True, cuts=True)

        prob.solve(solver)
        logger.info(f"Solver status: {pulp.LpStatus[prob.status]}")

        return prob, buy_vars, total_possible_cost

    def _create_failed_result(self) -> OptimizationResult:
        """Create a failed optimization result"""
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
