# backend/app/optimization/algorithms/evolutionary/nsga3_optimizer.py
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
import random
import pandas as pd
from collections import defaultdict
from functools import partial
import math
import itertools

from deap import algorithms, base, creator, tools
import numpy as np
import copy

from ...core.base_optimizer import BaseOptimizer, OptimizationResult
from ...preprocessing.penalty_calculator import PenaltyCalculator
from ...postprocessing.result_formatter import ResultFormatter
from app.constants import CardLanguage, CardQuality, CardVersion

logger = logging.getLogger(__name__)


class NSGA3Optimizer(BaseOptimizer):
    """Enhanced NSGA-III implementation with reference points and improved diversity"""

    def __init__(self, problem_data: Dict, config: Dict):
        super().__init__(problem_data, config)

        # Extract data from problem_data
        self.filtered_listings_df = problem_data["filtered_listings_df"]
        self.user_wishlist_df = problem_data["user_wishlist_df"]

        # Initialize components
        self.penalty_calculator = PenaltyCalculator(config)
        self.result_formatter = ResultFormatter()
        self.result_formatter.set_filtered_listings_df(self.filtered_listings_df)

        # Create optimization config
        self.optimization_config = self._create_optimization_config(config)

        # Initialize DEAP fitness and individual classes FIRST
        self._init_deap_classes()

        # Create card preferences
        self.card_preferences = {
            row["name"]: {
                "language": row.get("language", "English"),
                "quality": row.get("quality", "NM"),
                "version": row.get("version", "Standard"),
                "set_name": row.get("set_name", ""),
                "foil": row.get("foil", False),
            }
            for _, row in self.user_wishlist_df.iterrows()
        }

        # NSGA-III specific: Initialize reference points
        self.n_objectives = 3  # cost, quality, completeness (store_count incorporated into cost)
        self.ref_points = self._generate_reference_points()

    def _create_optimization_config(self, config: Dict):
        """Create optimization config object"""

        class MockOptimizationConfig:
            def __init__(self, config_dict):
                self.weights = config_dict.get("weights", {"cost": 1.0, "quality": 1.0, "store_count": 0.3})
                self.min_store = config_dict.get("min_store", 1)
                self.max_store = config_dict.get("max_store", 10)
                self.max_unique_store = config_dict.get("max_unique_store", 10)
                self.strict_preferences = config_dict.get("strict_preferences", False)
                self.high_cost = config_dict.get("high_cost", 10000.0)

        return MockOptimizationConfig(config)

    def _init_deap_classes(self):
        """Initialize DEAP classes for fitness and individuals"""
        weights = self.optimization_config.weights

        def safe_weight(w, fallback):
            return w if isinstance(w, (int, float)) and w > 0 else fallback

        # Use unique class names to avoid conflicts
        fitness_class_name = "FitnessMultiNSGA3"
        individual_class_name = "IndividualNSGA3"

        if not hasattr(creator, fitness_class_name):
            creator.create(
                fitness_class_name,
                base.Fitness,
                weights=(
                    -safe_weight(weights.get("cost"), 1.0),  # Minimize cost
                    safe_weight(weights.get("quality"), 1.0),  # Maximize quality
                    safe_weight(weights.get("completeness"), 1.0),  # Maximize completeness
                ),
            )
            logger.info(f"Created DEAP fitness class with weights: {weights}")

        if not hasattr(creator, individual_class_name):
            creator.create(individual_class_name, list, fitness=getattr(creator, fitness_class_name))

        self.fitness_class_name = fitness_class_name
        self.individual_class_name = individual_class_name

    def _generate_reference_points(self):
        """Generate reference points for NSGA-III using Das and Dennis method"""

        def das_dennis_reference_points(n_objectives, n_partitions):
            """Generate reference points using Das and Dennis method"""

            def generate_combinations(n_obj, n_part, current=[]):
                if n_obj == 1:
                    yield current + [n_part]
                else:
                    for i in range(n_part + 1):
                        yield from generate_combinations(n_obj - 1, n_part - i, current + [i])

            points = []
            for combination in generate_combinations(n_objectives, n_partitions):
                point = [x / n_partitions for x in combination]
                points.append(point)

            return np.array(points)

        # Generate reference points with appropriate granularity
        n_partitions = 12  # Adjustable parameter for granularity
        ref_points = das_dennis_reference_points(self.n_objectives, n_partitions)

        logger.info(f"Generated {len(ref_points)} reference points for NSGA-III")
        return ref_points

    def optimize(self) -> OptimizationResult:
        """Run improved NSGA-III optimization with data validation and debugging"""
        self._start_timing()
        self._update_progress(0.1, "Starting NSGA-III optimization")

        try:
            # VALIDATION: Check input data thoroughly
            logger.info(f"NSGA-III Data Validation:")
            logger.info(f"  User wishlist shape: {self.user_wishlist_df.shape}")
            logger.info(f"  Total quantity required: {self.user_wishlist_df['quantity'].sum()}")
            logger.info(f"  Unique cards required: {len(self.user_wishlist_df)}")
            logger.info(f"  Required cards: {list(self.user_wishlist_df['name'])}")

            logger.info(f"  Filtered listings shape: {self.filtered_listings_df.shape}")
            logger.info(f"  Unique cards available: {self.filtered_listings_df['name'].nunique()}")

            # Check card coverage
            required_cards = set(self.user_wishlist_df["name"])
            available_cards = set(self.filtered_listings_df["name"])
            missing_cards = required_cards - available_cards

            if missing_cards:
                logger.warning(f"Missing cards in listings: {missing_cards}")
            else:
                logger.info("✓ All required cards found in listings")

            # Log card availability details
            for _, card in self.user_wishlist_df.iterrows():
                card_name = card["name"]
                qty_required = card["quantity"]
                available_count = len(self.filtered_listings_df[self.filtered_listings_df["name"] == card_name])
                logger.info(f"  '{card_name}': need {qty_required}, found {available_count} listings")

            # Apply penalties to filtered listings
            self._update_progress(0.2, "Applying penalties to listings")
            original_count = len(self.filtered_listings_df)
            filtered_df = self.penalty_calculator.apply_penalties(
                self.filtered_listings_df, self.card_preferences, self.optimization_config.strict_preferences
            )

            logger.info(f"After penalty application: {len(filtered_df)} listings remain (was {original_count})")

            # Check if strict preferences filtered out too much
            retention_rate = len(filtered_df) / original_count if original_count > 0 else 0
            if retention_rate < 0.1:  # Less than 10% remain
                logger.warning(f"⚠️ Strict preferences filtered out {(1-retention_rate)*100:.1f}% of listings")
                logger.warning("Consider relaxing strict_preferences setting")

            # Validate we still have options for each card after filtering
            for _, card in self.user_wishlist_df.iterrows():
                card_name = card["name"]
                available_after_filter = len(filtered_df[filtered_df["name"] == card_name])
                if available_after_filter == 0:
                    logger.error(f"❌ No listings remain for '{card_name}' after filtering!")
                else:
                    logger.info(f"✓ '{card_name}': {available_after_filter} listings after filtering")

            # Run NSGA-III optimization
            self._update_progress(0.3, "Running NSGA-III evolution")
            best_solution, all_solutions = self._run_nsga_iii_optimization(filtered_df, self.user_wishlist_df)

            self._update_progress(1.0, "NSGA-III optimization completed")
            self._end_timing()

            if best_solution is not None:
                # Format solutions using result formatter
                standardized_best = self.result_formatter.format_solution(
                    best_solution, self.user_wishlist_df, filtered_df
                )

                standardized_iterations = []
                if all_solutions:
                    for solution in all_solutions[:20]:  # Limit to top 20 solutions
                        formatted_sol = self.result_formatter.format_solution(
                            solution, self.user_wishlist_df, filtered_df
                        )
                        if formatted_sol:
                            standardized_iterations.append(formatted_sol)

                return OptimizationResult(
                    best_solution=standardized_best,
                    all_solutions=standardized_iterations,
                    algorithm_used="NSGA-III-Enhanced",
                    execution_time=self.get_execution_time(),
                    iterations=len(standardized_iterations),
                    convergence_metric=0.0,  # Successful convergence
                    performance_stats=self.execution_stats,
                )
            else:
                return self._create_failed_result()

        except Exception as e:
            logger.error(f"NSGA-III optimization failed: {str(e)}")
            self._end_timing()
            return self._create_failed_result()

    def _evaluate_solution_wrapper(self, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame):
        """Create evaluation function for NSGA-III with detailed debugging"""

        def evaluate_solution(individual):
            # CLEAR INITIALIZATION: Get required card quantities from wishlist
            cards_required_total = int(user_wishlist_df["quantity"].sum())
            cards_required_by_name = {row["name"]: int(row["quantity"]) for _, row in user_wishlist_df.iterrows()}

            # DEBUGGING: Track what's happening in detail
            debug_info = {
                "individual_length": len(individual),
                "cards_required_total": cards_required_total,
                "invalid_indices": 0,
                "strict_filtered": 0,
                "cards_processed": 0,
                "cards_accepted": 0,
                "duplicate_cards": 0,
                "cards_by_name": defaultdict(int),
            }

            # CLEAR TRACKING: Initialize counters
            cards_found_total = 0
            cards_found_by_name = defaultdict(int)
            stores_used = set()
            total_cost = 0
            quality_scores = []

            for idx in individual:
                debug_info["cards_processed"] += 1

                if idx not in filtered_listings_df.index:
                    debug_info["invalid_indices"] += 1
                    continue

                card = filtered_listings_df.loc[idx]
                card_name = card["name"]
                debug_info["cards_by_name"][card_name] += 1

                # Check if we need more of this card
                required_qty = cards_required_by_name.get(card_name, 0)
                found_qty = cards_found_by_name[card_name]

                if found_qty >= required_qty:
                    debug_info["duplicate_cards"] += 1
                    continue  # Already have enough of this card

                # Count this card
                cards_found_total += 1
                cards_found_by_name[card_name] += 1

                # Calculate cost with penalties - IMPROVED ERROR HANDLING
                try:
                    final_price, total_multiplier, reason = self.penalty_calculator.compute_single_penalty(
                        card_data=card,
                        preferences=self.card_preferences.get(card["name"], {}),
                        config=self.optimization_config,
                    )

                    if reason == "strict_filter":
                        debug_info["strict_filtered"] += 1
                        # MODIFIED: Don't completely exclude, but heavily penalize
                        cards_found_total -= 1
                        cards_found_by_name[card_name] -= 1
                        continue

                    debug_info["cards_accepted"] += 1
                    total_cost += final_price
                    stores_used.add(card["site_name"])

                    # Compute quality score
                    normalized_quality = CardQuality.normalize(card.get("quality", "DMG"))
                    max_weight = max(CardQuality.get_weight(q.value) for q in CardQuality)
                    quality_score = 1 - (CardQuality.get_weight(normalized_quality) - 1) / (max_weight - 1)

                    language = CardLanguage.normalize(card.get("language", "Unknown"))
                    quality_score /= CardLanguage.get_weight(language)

                    quality_scores.append(quality_score)

                except Exception as e:
                    logger.warning(f"Penalty calculation failed for card {card_name}: {str(e)}")
                    # Use base price as fallback
                    base_price = float(card.get("price", 1000))
                    total_cost += base_price
                    stores_used.add(card["site_name"])
                    quality_scores.append(0.5)  # Default quality
                    debug_info["cards_accepted"] += 1

            # CLEAR CALCULATION: Calculate completeness metrics
            completeness_by_quantity = cards_found_total / cards_required_total if cards_required_total > 0 else 0.0
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            store_count = len(stores_used)

            # DEBUGGING: Log detailed info for first few evaluations
            if not hasattr(self, "_eval_count"):
                self._eval_count = 0
            self._eval_count += 1

            if self._eval_count <= 3:  # Log first 3 evaluations in detail
                logger.info(f"🔍 NSGA-III Evaluation #{self._eval_count} Debug:")
                logger.info(f"  Individual length: {debug_info['individual_length']}")
                logger.info(f"  Cards required total: {debug_info['cards_required_total']}")
                logger.info(f"  Cards processed: {debug_info['cards_processed']}")
                logger.info(f"  Invalid indices: {debug_info['invalid_indices']}")
                logger.info(f"  Strict filtered: {debug_info['strict_filtered']}")
                logger.info(f"  Duplicate cards: {debug_info['duplicate_cards']}")
                logger.info(f"  Cards accepted: {debug_info['cards_accepted']}")
                logger.info(f"  Cards found total: {cards_found_total}")
                logger.info(f"  Completeness: {completeness_by_quantity:.2%}")
                logger.info(f"  Total cost: ${total_cost:.2f}")
                logger.info(f"  Stores used: {store_count}")
                # logger.info(f"  Cards by name: {dict(debug_info['cards_by_name'])}")
                # logger.info(f"  Found by name: {dict(cards_found_by_name)}")

            # Apply penalties for constraint violations with store count penalty
            if store_count > self.optimization_config.max_unique_store:
                store_penalty = (store_count - self.optimization_config.max_unique_store) * 500
                total_cost += store_penalty

            # MODIFIED: More forgiving incompleteness penalty
            if completeness_by_quantity < 1.0:
                # Scale penalty based on how close we are to completion
                incompleteness_factor = 1 - completeness_by_quantity
                base_penalty = cards_required_total * 50
                scaled_penalty = base_penalty * (incompleteness_factor**2)
                total_cost += scaled_penalty

            # Return 3 objectives for NSGA-III (consistent with fitness class)
            return (
                total_cost,  # Cost objective (minimize) - includes store count penalty
                avg_quality,  # Quality objective (maximize)
                completeness_by_quantity,  # Completeness objective (maximize)
            )

        return evaluate_solution

    def _normalize_objectives(self, population):
        """Normalize objectives for reference point comparison"""
        objectives = np.array([ind.fitness.values for ind in population])

        # Handle empty population
        if len(objectives) == 0:
            return objectives

        # Find ideal and nadir points
        ideal_point = np.min(objectives, axis=0)
        nadir_point = np.max(objectives, axis=0)

        # Avoid division by zero
        ranges = nadir_point - ideal_point
        ranges[ranges == 0] = 1.0

        # Normalize
        normalized = (objectives - ideal_point) / ranges
        return normalized

    def _associate_to_reference_points(self, population, normalized_objectives):
        """Associate individuals to reference points"""
        if len(population) == 0 or len(normalized_objectives) == 0:
            return {i: [] for i in range(len(self.ref_points))}

        associations = {i: [] for i in range(len(self.ref_points))}

        for idx, obj in enumerate(normalized_objectives):
            # Find closest reference point
            distances = np.linalg.norm(self.ref_points - obj, axis=1)
            closest_ref = np.argmin(distances)
            associations[closest_ref].append(idx)

        return associations

    def _reference_point_selection(self, population, k):
        """Select k individuals using reference point based selection"""
        if len(population) <= k:
            return population

        # Normalize objectives
        normalized_objectives = self._normalize_objectives(population)

        # Associate individuals to reference points
        associations = self._associate_to_reference_points(population, normalized_objectives)

        # Count how many individuals are associated with each reference point
        niche_counts = {ref_idx: len(individuals) for ref_idx, individuals in associations.items()}

        selected = []
        remaining_population = list(range(len(population)))

        while len(selected) < k and remaining_population:
            # Find reference point with minimum niche count
            min_niche_count = min(
                niche_counts[ref_idx]
                for ref_idx in associations.keys()
                if any(idx in remaining_population for idx in associations[ref_idx])
            )

            # Get reference points with minimum niche count
            min_niche_refs = [
                ref_idx
                for ref_idx, count in niche_counts.items()
                if count == min_niche_count and any(idx in remaining_population for idx in associations[ref_idx])
            ]

            if not min_niche_refs:
                break

            # Randomly select one reference point
            selected_ref = random.choice(min_niche_refs)

            # Get available individuals for this reference point
            available_individuals = [idx for idx in associations[selected_ref] if idx in remaining_population]

            if available_individuals:
                # Select individual closest to reference point
                if min_niche_count == 0:
                    # If no individual associated yet, select closest
                    ref_point = self.ref_points[selected_ref]
                    distances = [
                        np.linalg.norm(normalized_objectives[idx] - ref_point) for idx in available_individuals
                    ]
                    best_idx = available_individuals[np.argmin(distances)]
                else:
                    # Random selection from associated individuals
                    best_idx = random.choice(available_individuals)

                selected.append(best_idx)
                remaining_population.remove(best_idx)
                niche_counts[selected_ref] += 1
            else:
                # No available individuals for this reference point
                break

        # Return selected individuals
        return [population[idx] for idx in selected[:k]]

    def _run_nsga_iii_optimization(
        self, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame, milp_solution: Optional[List] = None
    ) -> Tuple[Optional[List], Optional[List]]:
        """Enhanced NSGA-III with reference point based selection"""

        # CLEAR INITIALIZATION: Get required card quantities
        cards_required_total = int(user_wishlist_df["quantity"].sum())
        cards_required_unique = len(user_wishlist_df)

        logger.info(
            f"NSGA-III starting with {cards_required_total} total cards needed ({cards_required_unique} unique)"
        )
        logger.info(f"Using {len(self.ref_points)} reference points")

        # RELAXED PARAMETERS: More forgiving thresholds
        NGEN = 100
        POP_SIZE = 300  # Should be multiple of reference points for best results
        TOURNAMENT_SIZE = 3
        CXPB = 0.85
        MUTPB = 0.15
        COMPLETENESS_THRESHOLD = 0.90  # Lowered from 0.999 to 0.90 (90%)

        logger.info(f"Using relaxed completeness threshold: {COMPLETENESS_THRESHOLD:.1%}")

        # Initialize toolbox
        toolbox = self._initialize_toolbox(filtered_listings_df, user_wishlist_df)

        # Initialize population
        logger.info("Initializing population...")
        if milp_solution:
            logger.info("Integrating MILP solution into initial population")
            pop = self._initialize_population_with_milp(POP_SIZE, filtered_listings_df, user_wishlist_df, milp_solution)
            if pop is None:
                pop = toolbox.population(n=POP_SIZE)
        else:
            pop = toolbox.population(n=POP_SIZE)

        if not pop:
            logger.error("Failed to initialize population")
            return None, None

        # Initialize tracking variables
        best_solution = None
        best_fitness_cost = float("inf")
        best_completeness = 0.0
        generations_without_improvement = 0
        archive = tools.ParetoFront()

        # Evaluate initial population with detailed logging
        logger.info("Evaluating initial population...")
        fitnesses = [toolbox.evaluate(ind) for ind in pop]

        initial_completeness_stats = []
        for ind, fit in zip(pop, fitnesses):
            ind.fitness.values = fit
            if len(fit) >= 3:
                initial_completeness_stats.append(fit[2])

        if initial_completeness_stats:
            logger.info(f"Initial population completeness stats:")
            logger.info(f"  Best: {max(initial_completeness_stats):.2%}")
            logger.info(f"  Average: {sum(initial_completeness_stats)/len(initial_completeness_stats):.2%}")
            logger.info(
                f"  Above {COMPLETENESS_THRESHOLD:.0%}: {sum(1 for c in initial_completeness_stats if c >= COMPLETENESS_THRESHOLD)}"
            )

        # Track best solution from initial population
        for ind, fit in zip(pop, fitnesses):
            try:
                if len(fit) >= 3:
                    cost, quality, completeness = fit

                    # More lenient best solution tracking
                    is_better = False
                    if completeness >= COMPLETENESS_THRESHOLD:  # Good enough solution
                        if best_completeness < COMPLETENESS_THRESHOLD:  # We didn't have a good solution before
                            is_better = True
                        elif cost < best_fitness_cost:  # We had a good solution, check cost
                            is_better = True
                    elif completeness > best_completeness:  # Both not good enough, prefer higher completeness
                        is_better = True

                    if is_better:
                        best_fitness_cost = cost
                        best_completeness = completeness
                        best_solution = self._safe_clone_individual(toolbox, ind)
                        logger.info(f"Initial best: ${cost:.2f}, completeness: {completeness:.1%}")

            except Exception as e:
                logger.warning(f"Error tracking best solution: {str(e)}")

        # Update archive with initial population
        try:
            archive.update(pop)
        except Exception as e:
            logger.warning(f"Error updating archive: {str(e)}")

        # Evolution loop with NSGA-III selection
        for gen in range(NGEN):
            try:
                self._update_progress(0.5, f"Generation {gen}")

                # Generate offspring
                offspring = []
                while len(offspring) < POP_SIZE:
                    try:
                        # Select parents
                        parents = tools.selTournament(pop, k=2, tournsize=TOURNAMENT_SIZE)
                        parent1, parent2 = parents[0], parents[1] if len(parents) > 1 else parents[0]

                        # Crossover and mutation
                        if random.random() < CXPB:
                            child1, child2 = toolbox.mate(
                                self._safe_clone_individual(toolbox, parent1),
                                self._safe_clone_individual(toolbox, parent2),
                            )

                            if random.random() < MUTPB:
                                child1 = toolbox.mutate(child1)[0]
                            if random.random() < MUTPB:
                                child2 = toolbox.mutate(child2)[0]

                            # Clear fitness for re-evaluation
                            if hasattr(child1, "fitness"):
                                del child1.fitness.values
                            if hasattr(child2, "fitness"):
                                del child2.fitness.values

                            offspring.extend([child1, child2])

                    except Exception as e:
                        logger.warning(f"Error generating offspring: {str(e)}")
                        continue

                # Trim offspring to exact size needed
                offspring = offspring[:POP_SIZE]

                # Evaluate offspring
                for ind in offspring:
                    try:
                        if not hasattr(ind.fitness, "values") or not ind.fitness.valid:
                            fitness = toolbox.evaluate(ind)
                            if len(fitness) == 3:
                                ind.fitness.values = fitness
                            else:
                                ind.fitness.values = (float("inf"), 0.0, 0.0)

                        # CLEAR TRACKING: Update best solution using relaxed threshold
                        fit = ind.fitness.values
                        if len(fit) >= 3:
                            cost, quality, completeness = fit

                            is_better = False
                            if completeness >= COMPLETENESS_THRESHOLD:  # Good enough solution
                                if best_completeness < COMPLETENESS_THRESHOLD:  # We didn't have a good solution before
                                    is_better = True
                                elif cost < best_fitness_cost:  # We had a good solution, check cost
                                    is_better = True
                            elif completeness > best_completeness:  # Both not good enough, prefer higher completeness
                                is_better = True

                            if is_better:
                                best_fitness_cost = cost
                                best_completeness = completeness
                                best_solution = self._safe_clone_individual(toolbox, ind)
                                generations_without_improvement = 0
                                logger.info(f"Gen {gen}: New best - ${cost:.2f}, completeness: {completeness:.1%}")

                    except Exception as e:
                        logger.warning(f"Error evaluating offspring: {str(e)}")
                        if hasattr(ind, "fitness"):
                            ind.fitness.values = (float("inf"), 0.0, 0.0)

                # Combine populations
                combined_pop = pop + offspring

                # Non-dominated sorting
                try:
                    fronts = tools.sortNondominated(combined_pop, POP_SIZE, first_front_only=False)
                except Exception as e:
                    logger.warning(f"Error in non-dominated sorting: {str(e)}")
                    fronts = [combined_pop[:POP_SIZE]]  # Fallback

                # Select next generation using NSGA-III
                new_pop = []
                for front in fronts:
                    if len(new_pop) + len(front) <= POP_SIZE:
                        new_pop.extend(front)
                    else:
                        # Use reference point based selection for the last front
                        remaining_slots = POP_SIZE - len(new_pop)
                        try:
                            selected = self._reference_point_selection(front, remaining_slots)
                            new_pop.extend(selected)
                        except Exception as e:
                            logger.warning(f"Error in reference point selection: {str(e)}")
                            # Fallback to random selection
                            new_pop.extend(random.sample(front, remaining_slots))
                        break

                pop = new_pop

                try:
                    archive.update(pop)
                except Exception as e:
                    logger.warning(f"Error updating archive: {str(e)}")

                # ENHANCED LOGGING: More detailed progress with relaxed threshold
                try:
                    good_in_pop = sum(
                        1
                        for ind in pop
                        if hasattr(ind, "fitness")
                        and hasattr(ind.fitness, "values")
                        and len(ind.fitness.values) >= 3
                        and ind.fitness.values[2] >= COMPLETENESS_THRESHOLD
                    )

                    if gen % 10 == 0:
                        logger.info(f"Gen {gen}:")
                        logger.info(f"  Good solutions (≥{COMPLETENESS_THRESHOLD:.0%}) in population: {good_in_pop}")
                        logger.info(f"  Best completeness: {best_completeness:.1%}")
                        logger.info(f"  Best cost: ${best_fitness_cost:.2f}")
                        logger.info(f"  Generations without improvement: {generations_without_improvement}")

                    # More lenient convergence check
                    generations_without_improvement += 1
                    if generations_without_improvement >= 30:  # Increased from 20
                        logger.info(f"Converged after {gen} generations without improvement")
                        break

                except Exception as e:
                    logger.warning(f"Error in progress logging: {str(e)}")

            except Exception as e:
                logger.error(f"Error in generation {gen}: {str(e)}")
                continue

        # Extract final results with relaxed threshold
        try:
            if (
                best_solution is not None
                and hasattr(best_solution, "fitness")
                and hasattr(best_solution.fitness, "values")
            ):
                fitness_vals = best_solution.fitness.values
                if len(fitness_vals) >= 3:
                    cost, quality, completeness = fitness_vals
                    logger.info(f"Final NSGA-III Solution:")
                    logger.info(f"  Cost: ${cost:.2f}")
                    logger.info(f"  Completeness: {completeness:.1%}")
                    logger.info(f"  Quality: {quality:.3f}")

                    # Extract solutions using relaxed threshold
                    all_solutions = []
                    for ind in archive:
                        try:
                            if (
                                hasattr(ind, "fitness")
                                and hasattr(ind.fitness, "values")
                                and len(ind.fitness.values) >= 3
                                and ind.fitness.values[2] >= COMPLETENESS_THRESHOLD  # Using relaxed threshold
                            ):
                                all_solutions.append(list(ind))
                        except Exception as e:
                            logger.warning(f"Error processing archive individual: {str(e)}")
                            continue

                    # Sort by cost
                    try:
                        all_solutions = sorted(
                            all_solutions,
                            key=lambda x: self._safe_get_fitness_cost(x, filtered_listings_df, user_wishlist_df),
                        )
                    except Exception as e:
                        logger.warning(f"Error sorting solutions: {str(e)}")

                    logger.info(f"Found {len(all_solutions)} good solutions (≥{COMPLETENESS_THRESHOLD:.0%}) in archive")
                    return list(best_solution), all_solutions

        except Exception as e:
            logger.error(f"Error extracting final results: {str(e)}")

        logger.warning(f"No solutions found meeting {COMPLETENESS_THRESHOLD:.0%} completeness threshold")
        return None, None

    def _initialize_individual_smart(self, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame):
        """Smart individual initialization with extensive validation and debugging"""
        individual = []
        expected_length = sum(user_wishlist_df["quantity"])

        # logger.info(f"🔧 Initializing individual with expected length: {expected_length}")

        cards_added = 0
        initialization_stats = {
            "cards_with_options": 0,
            "cards_without_options": 0,
            "total_options_found": 0,
            "errors": 0,
        }

        for _, card in user_wishlist_df.iterrows():
            card_name = card["name"]
            required_quantity = int(card.get("quantity", 1))

            # Find available options for this card
            available_options = filtered_listings_df[filtered_listings_df["name"] == card_name]

            initialization_stats["total_options_found"] += len(available_options)

            if not available_options.empty:
                initialization_stats["cards_with_options"] += 1
                # logger.info(f"  ✓ '{card_name}': need {required_quantity}, found {len(available_options)} options")

                # Add required quantity of this card
                for copy_num in range(required_quantity):
                    try:
                        # Use weighted selection for quality/price ratio
                        weights = []
                        for _, row in available_options.iterrows():
                            try:
                                quality_weight = CardQuality.get_weight(
                                    CardQuality.normalize(row.get("quality", "DMG"))
                                )
                                price = float(row.get("price", 1000))
                                # Higher weight = better choice
                                weight = quality_weight / (price + 0.1)
                                weights.append(weight)
                            except:
                                weights.append(1.0)  # Default weight

                        if len(weights) == len(available_options):
                            selected_option = available_options.sample(n=1, weights=weights)
                            individual.append(selected_option.index.item())
                        else:
                            # Fallback to simple random selection
                            individual.append(random.choice(available_options.index))

                        cards_added += 1

                    except Exception as e:
                        logger.warning(f"Error selecting copy {copy_num+1} for {card_name}: {str(e)}")
                        initialization_stats["errors"] += 1
                        # Fallback to first available option
                        individual.append(available_options.index[0])
                        cards_added += 1
            else:
                initialization_stats["cards_without_options"] += 1
                logger.warning(f"  ❌ '{card_name}': need {required_quantity}, found 0 options")
                logger.warning(f"     Using random fallback for {required_quantity} copies")

                # Fallback: random selection from all listings
                for _ in range(required_quantity):
                    individual.append(random.randint(0, len(filtered_listings_df) - 1))
                    cards_added += 1

        # Final validation and adjustment
        # logger.info(f"🔧 Initialization complete:")
        # logger.info(f"  Cards with options: {initialization_stats['cards_with_options']}")
        # logger.info(f"  Cards without options: {initialization_stats['cards_without_options']}")
        # logger.info(f"  Total options found: {initialization_stats['total_options_found']}")
        # logger.info(f"  Errors encountered: {initialization_stats['errors']}")
        # logger.info(f"  Cards added: {cards_added}, expected: {expected_length}")

        if len(individual) != expected_length:
            logger.warning(f"⚠️ Individual length mismatch: {len(individual)} != {expected_length}")
            if len(individual) < expected_length:
                shortage = expected_length - len(individual)
                logger.info(f"  Adding {shortage} random cards to reach expected length")
                individual.extend([random.randint(0, len(filtered_listings_df) - 1) for _ in range(shortage)])
            else:
                logger.info(f"  Trimming to expected length")
                individual = individual[:expected_length]

        # logger.info(f"✓ Final individual length: {len(individual)}")
        return getattr(creator, self.individual_class_name)(individual)

    def _safe_get_fitness_cost(self, individual, filtered_listings_df, user_wishlist_df):
        """Safely get fitness cost for sorting with consistent evaluation"""
        try:
            if hasattr(individual, "fitness") and hasattr(individual.fitness, "values"):
                return individual.fitness.values[0]
            else:
                # Evaluate if no fitness available
                eval_func = self._evaluate_solution_wrapper(filtered_listings_df, user_wishlist_df)
                fitness = eval_func(individual)
                return fitness[0] if len(fitness) > 0 else float("inf")
        except Exception as e:
            logger.warning(f"Error getting fitness cost: {str(e)}")
            return float("inf")

    def _safe_clone_individual(self, toolbox, individual):
        """Safely clone an individual preserving fitness values"""
        try:
            # Create a deep copy to ensure fitness is preserved
            cloned = copy.deepcopy(individual)
            return cloned
        except Exception as e:
            logger.warning(f"Deep copy failed, trying alternative clone: {str(e)}")
            try:
                # Fallback to manual cloning
                individual_class = getattr(creator, self.individual_class_name)
                cloned = individual_class(individual[:])
                if hasattr(individual, "fitness") and hasattr(individual.fitness, "values"):
                    cloned.fitness.values = individual.fitness.values
                return cloned
            except Exception as e2:
                logger.error(f"All cloning methods failed: {str(e2)}")
                return individual

    def _initialize_toolbox(self, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame):
        """Initialize DEAP toolbox with operators"""
        toolbox = base.Toolbox()

        # Individual and population initialization
        expected_length = sum(user_wishlist_df["quantity"])
        toolbox.register("attr_idx", random.randint, 0, len(filtered_listings_df) - 1)

        # Register the individual creation function correctly
        toolbox.register(
            "individual",
            self._initialize_individual_smart,
            filtered_listings_df=filtered_listings_df,
            user_wishlist_df=user_wishlist_df,
        )
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)

        # Genetic operators
        toolbox.register("evaluate", self._evaluate_solution_wrapper(filtered_listings_df, user_wishlist_df))
        toolbox.register("mate", self._smart_crossover)
        toolbox.register(
            "mutate",
            partial(
                self._smart_mutation,
                filtered_listings_df=filtered_listings_df,
                user_wishlist_df=user_wishlist_df,
            ),
        )
        toolbox.register("select", tools.selNSGA2)  # Still use NSGA2 sorting, but with reference point selection
        toolbox.register("clone", lambda ind: getattr(creator, self.individual_class_name)(ind[:]))

        return toolbox

    def _smart_crossover(self, ind1, ind2):
        """Enhanced crossover that preserves card structure"""
        if len(ind1) > 2:
            # Two-point crossover with card boundaries
            point1 = random.randint(1, len(ind1) // 2)
            point2 = random.randint(len(ind1) // 2, len(ind1) - 1)

            # Swap segments
            ind1[point1:point2], ind2[point1:point2] = ind2[point1:point2], ind1[point1:point2]

        return ind1, ind2

    def _smart_mutation(
        self, individual, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame, indpb: float = 0.05
    ):
        """Smart mutation that considers card requirements"""
        card_positions = {}
        position = 0

        # Map positions to cards
        for _, card in user_wishlist_df.iterrows():
            card_name = card["name"]
            quantity = int(card.get("quantity", 1))
            card_positions[card_name] = list(range(position, position + quantity))
            position += quantity

        for i in range(len(individual)):
            if random.random() < indpb:
                # Find which card this position corresponds to
                card_name = None
                for name, positions in card_positions.items():
                    if i in positions:
                        card_name = name
                        break

                if card_name:
                    # Get available options for this card
                    available_options = filtered_listings_df[filtered_listings_df["name"] == card_name]
                    if not available_options.empty:
                        # Weight by quality/price ratio
                        weights = []
                        for _, row in available_options.iterrows():
                            quality_weight = CardQuality.get_weight(CardQuality.normalize(row.get("quality", "DMG")))
                            price = float(row.get("price", 1000))
                            weight = quality_weight / (price + 0.1)
                            weights.append(weight)

                        new_option = available_options.sample(n=1, weights=weights)
                        individual[i] = new_option.index.item()
                    else:
                        # Fallback to random
                        individual[i] = random.randint(0, len(filtered_listings_df) - 1)

        return (individual,)

    def _initialize_population_with_milp(
        self, n: int, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame, milp_solution: List
    ) -> Optional[List]:
        """Initialize population using MILP solution as seed"""
        try:
            elite_size = max(1, n // 10)

            # Convert MILP solution to indices
            milp_indices = self._convert_solution_to_indices(milp_solution, filtered_listings_df)

            if milp_indices is None:
                logger.warning("Failed to convert MILP solution, using random population")
                return None

            # Validate length
            expected_length = sum(user_wishlist_df["quantity"])
            if len(milp_indices) != expected_length:
                logger.warning(f"MILP solution length mismatch: {len(milp_indices)} != {expected_length}")
                return None

            population = []

            # Add MILP solution variants
            for _ in range(elite_size):
                variant = getattr(creator, self.individual_class_name)(milp_indices[:])
                if random.random() < 0.5:  # 50% chance to mutate
                    variant = self._smart_mutation(variant, filtered_listings_df, user_wishlist_df, indpb=0.1)[0]
                population.append(variant)

            # Create remaining individuals with bias towards MILP stores
            milp_stores = set(x.get("site_name", "") for x in milp_solution)

            for _ in range(n - elite_size):
                try:
                    new_ind = self._initialize_individual_biased(filtered_listings_df, user_wishlist_df, milp_stores)
                    if new_ind is not None:
                        population.append(new_ind)
                except Exception as e:
                    logger.warning(f"Failed to initialize biased individual: {str(e)}")

            logger.info(f"Created population of {len(population)} individuals with MILP seeding")
            return population if len(population) >= n // 2 else None

        except Exception as e:
            logger.error(f"Error in _initialize_population_with_milp: {str(e)}")
            return None

    def _convert_solution_to_indices(
        self, solution: List[Dict], filtered_listings_df: pd.DataFrame
    ) -> Optional[List[int]]:
        """Convert MILP solution to indices for genetic algorithm"""
        indices = []

        # Ensure price columns are rounded to same precision
        if "price" in filtered_listings_df.columns:
            filtered_listings_df["price"] = filtered_listings_df["price"].round(2)

        for record in solution:
            record_price = round(float(record.get("price", 0.0)), 2)

            # Match by name, store, and price
            mask = (
                (filtered_listings_df["name"] == record["name"])
                & (filtered_listings_df["site_name"] == record["site_name"])
                & (abs(filtered_listings_df["price"] - record_price) < 0.01)
            )
            matching_rows = filtered_listings_df[mask]

            if matching_rows.empty:
                # Try more lenient search
                alternate_mask = (filtered_listings_df["name"] == record["name"]) & (
                    filtered_listings_df["site_name"] == record["site_name"]
                )
                alternate_rows = filtered_listings_df[alternate_mask]

                if not alternate_rows.empty:
                    closest_match = alternate_rows.iloc[(alternate_rows["price"] - record_price).abs().argmin()]
                    indices.append(closest_match.name)
                else:
                    logger.warning(f"Could not match {record['name']} at {record['site_name']}")
                    continue
            else:
                indices.append(matching_rows.index[0])

        return indices if indices else None

    def _initialize_individual_biased(
        self, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame, preferred_stores: set
    ) -> Optional[Any]:
        """Initialize individual with bias towards preferred stores"""
        individual = []
        expected_length = sum(user_wishlist_df["quantity"])

        for _, card in user_wishlist_df.iterrows():
            card_name = card["name"]
            required_quantity = int(card.get("quantity", 1))

            # First try preferred stores
            preferred_options = filtered_listings_df[
                (filtered_listings_df["name"] == card_name) & (filtered_listings_df["site_name"].isin(preferred_stores))
            ]

            # Fallback to all stores if no preferred options
            if preferred_options.empty:
                available_options = filtered_listings_df[filtered_listings_df["name"] == card_name]
            else:
                available_options = preferred_options

            if not available_options.empty:
                for _ in range(required_quantity):
                    # Weight by quality/price ratio
                    weights = []
                    for _, row in available_options.iterrows():
                        quality_weight = CardQuality.get_weight(CardQuality.normalize(row.get("quality", "DMG")))
                        price = float(row.get("price", 1000))
                        weight = quality_weight / (price + 0.1)
                        weights.append(weight)

                    selected_option = available_options.sample(n=1, weights=weights)
                    individual.append(selected_option.index.item())

        if len(individual) != expected_length:
            logger.warning(f"Individual length mismatch: {len(individual)} != {expected_length}")
            return None

        return getattr(creator, self.individual_class_name)(individual)

    def _create_failed_result(self) -> OptimizationResult:
        """Create a failed optimization result"""
        return OptimizationResult(
            best_solution={},
            all_solutions=[],
            algorithm_used="NSGA-III-Enhanced",
            execution_time=self.get_execution_time(),
            iterations=0,
            convergence_metric=1.0,
            performance_stats=self.execution_stats,
        )

    def get_algorithm_name(self) -> str:
        return "NSGA-III-Enhanced"
