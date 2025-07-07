# backend/app/optimization/algorithms/evolutionary/moead_optimizer.py
from typing import Dict, List, Optional, Tuple, Any
import logging
import random
import numpy as np
import pandas as pd
from collections import defaultdict
from functools import partial
import math
import uuid

from deap import base, creator, tools

from ...core.base_optimizer import BaseOptimizer, OptimizationResult
from ...preprocessing.penalty_calculator import PenaltyCalculator
from ...postprocessing.result_formatter import ResultFormatter
from app.constants import CardLanguage, CardQuality, CardVersion

logger = logging.getLogger(__name__)


class MOEADOptimizer(BaseOptimizer):
    """
    Multi-Objective Evolutionary Algorithm based on Decomposition (MOEA/D)

    MOEA/D decomposes a multi-objective optimization problem into a number of
    scalar optimization subproblems and optimizes them simultaneously using
    information from neighboring subproblems.
    """

    def __init__(self, problem_data: Dict, config: Dict):
        super().__init__(problem_data, config)

        # Generate unique class names to avoid conflicts
        self.unique_id = str(uuid.uuid4()).replace("-", "")[:8]
        self.fitness_class_name = f"FitnessMultiMOEAD{self.unique_id}"
        self.individual_class_name = f"IndividualMOEAD{self.unique_id}"

        # Extract data from problem_data
        self.filtered_listings_df = problem_data["filtered_listings_df"]
        self.user_wishlist_df = problem_data["user_wishlist_df"]

        # Initialize components with config
        self.penalty_calculator = PenaltyCalculator(config)
        self.result_formatter = ResultFormatter()

        # Create optimization config
        self.optimization_config = self._create_optimization_config(config)

        # MOEA/D specific parameters
        self.n_objectives = 4  # cost, quality, completeness, store_count
        self.population_size = config.get("population_size", 100)  # Reduced for stability
        self.neighborhood_size = min(config.get("neighborhood_size", 20), self.population_size // 2)
        self.max_generations = config.get("max_generations", 100)  # Reduced for faster execution
        self.decomposition_method = config.get("decomposition_method", "tchebycheff")

        # Initialize DEAP classes FIRST
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

        # Initialize weight vectors and neighborhoods
        self.weight_vectors = self._generate_weight_vectors()
        self.neighborhoods = self._calculate_neighborhoods()

        logger.info(f"MOEA/D initialized with {len(self.weight_vectors)} weight vectors")

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
        """Initialize DEAP classes for fitness and individuals with unique names"""
        try:
            # Only create if they don't already exist
            if not hasattr(creator, self.fitness_class_name):
                # MOEA/D uses minimization for all objectives
                creator.create(self.fitness_class_name, base.Fitness, weights=(-1.0, -1.0, -1.0, -1.0))
                logger.debug(f"Created fitness class: {self.fitness_class_name}")

            if not hasattr(creator, self.individual_class_name):
                creator.create(self.individual_class_name, list, fitness=getattr(creator, self.fitness_class_name))
                logger.debug(f"Created individual class: {self.individual_class_name}")

        except Exception as e:
            logger.error(f"Failed to initialize DEAP classes: {str(e)}")
            raise

    def _generate_weight_vectors(self) -> np.ndarray:
        """Generate uniformly distributed weight vectors using simplified approach"""
        try:
            # Use a simpler approach for weight vector generation
            weights = []

            # Generate weight vectors using uniform distribution
            for i in range(self.population_size):
                weight = np.random.dirichlet(np.ones(self.n_objectives))
                weights.append(weight)

            weight_array = np.array(weights)

            # Ensure we have exactly the right number of weight vectors
            if len(weight_array) != self.population_size:
                weight_array = weight_array[: self.population_size]
                if len(weight_array) < self.population_size:
                    # Add more random weights if needed
                    additional_needed = self.population_size - len(weight_array)
                    additional_weights = np.random.dirichlet(np.ones(self.n_objectives), additional_needed)
                    weight_array = np.vstack([weight_array, additional_weights])

            logger.info(f"Generated {len(weight_array)} weight vectors for MOEA/D")
            return weight_array

        except Exception as e:
            logger.error(f"Failed to generate weight vectors: {str(e)}")
            # Fallback to simple uniform weights
            weights = []
            for i in range(self.population_size):
                weight = [1.0 / self.n_objectives] * self.n_objectives
                weights.append(weight)
            return np.array(weights)

    def _calculate_neighborhoods(self) -> List[List[int]]:
        """Calculate neighborhoods based on Euclidean distance between weight vectors"""
        neighborhoods = []

        try:
            for i in range(len(self.weight_vectors)):
                # Calculate distances to all other weight vectors
                distances = []
                for j in range(len(self.weight_vectors)):
                    if i != j:
                        dist = np.linalg.norm(self.weight_vectors[i] - self.weight_vectors[j])
                        distances.append((dist, j))

                # Sort by distance and take closest neighbors
                distances.sort()
                neighborhood_size = min(self.neighborhood_size - 1, len(distances))
                neighborhood = [i] + [idx for _, idx in distances[:neighborhood_size]]
                neighborhoods.append(neighborhood)

            return neighborhoods

        except Exception as e:
            logger.error(f"Failed to calculate neighborhoods: {str(e)}")
            # Fallback to simple neighborhoods
            neighborhoods = []
            for i in range(len(self.weight_vectors)):
                # Simple circular neighborhood
                neighborhood = []
                for j in range(self.neighborhood_size):
                    idx = (i + j) % len(self.weight_vectors)
                    neighborhood.append(idx)
                neighborhoods.append(neighborhood)
            return neighborhoods

    def optimize(self) -> OptimizationResult:
        """Run MOEA/D optimization"""
        self._start_timing()
        self._update_progress(0.1, "Starting MOEA/D optimization")

        try:
            logger.info(f"MOEA/D Problem Summary:")
            logger.info(f"  Cards: {len(self.user_wishlist_df)}")
            logger.info(f"  Listings: {len(self.filtered_listings_df)}")
            logger.info(f"  Population size: {self.population_size}")

            # Apply penalties to filtered listings
            self._update_progress(0.2, "Applying penalties to listings")
            filtered_df = self.penalty_calculator.apply_penalties(
                self.filtered_listings_df, self.card_preferences, self.optimization_config.strict_preferences
            )

            # Run MOEA/D optimization
            self._update_progress(0.3, "Running MOEA/D evolution")
            best_solutions, pareto_front = self._run_moead_optimization(filtered_df, self.user_wishlist_df)

            self._end_timing()
            self._update_progress(0.9, "Formatting results")

            if best_solutions:
                # Select best solution from results
                best_solution = self._select_best_from_results(best_solutions, filtered_df)

                # Format solutions using result formatter
                standardized_best = self.result_formatter.format_solution(
                    best_solution, self.user_wishlist_df, filtered_df
                )

                standardized_iterations = []
                if pareto_front:
                    for solution in pareto_front[:10]:  # Limit to top 10 solutions
                        try:
                            formatted_sol = self.result_formatter.format_solution(
                                solution, self.user_wishlist_df, filtered_df
                            )
                            if formatted_sol:
                                standardized_iterations.append(formatted_sol)
                        except Exception as e:
                            logger.warning(f"Failed to format solution: {str(e)}")
                            continue

                self._update_progress(1.0, "MOEA/D optimization completed")

                return OptimizationResult(
                    best_solution=standardized_best,
                    all_solutions=standardized_iterations,
                    algorithm_used="MOEA/D",
                    execution_time=self.get_execution_time(),
                    iterations=len(standardized_iterations),
                    convergence_metric=0.0,  # Successful convergence
                    performance_stats=self.execution_stats,
                )
            else:
                logger.warning("MOEA/D produced no valid solutions")
                return self._create_failed_result()

        except Exception as e:
            logger.error(f"MOEA/D optimization failed: {str(e)}", exc_info=True)
            self._end_timing()
            return self._create_failed_result()

    def _select_best_from_results(self, solutions: List, filtered_df: pd.DataFrame) -> List:
        """Select best solution from results with consistent card quantity tracking"""
        if not solutions:
            return None

        # CLEAR INITIALIZATION: Get required card quantities from wishlist
        cards_required_total = int(self.user_wishlist_df["quantity"].sum())
        cards_required_by_name = {row["name"]: int(row["quantity"]) for _, row in self.user_wishlist_df.iterrows()}

        # Evaluate each solution and select best
        best_solution = None
        best_score = float("-inf")

        for solution in solutions:
            try:
                # CLEAR TRACKING: Calculate solution metrics consistently
                stores_used = set()
                total_cost = 0
                cards_found_by_name = defaultdict(int)
                cards_found_total = 0

                for idx in solution:
                    if idx in filtered_df.index:
                        card = filtered_df.loc[idx]
                        card_name = card["name"]

                        # Check if we need more of this card
                        required_qty = cards_required_by_name.get(card_name, 0)
                        found_qty = cards_found_by_name[card_name]

                        if found_qty < required_qty:
                            stores_used.add(card["site_name"])
                            total_cost += card.get("weighted_price", card.get("price", 0))
                            cards_found_by_name[card_name] += 1
                            cards_found_total += 1

                # CLEAR CALCULATION: Calculate completeness
                completeness_by_quantity = cards_found_total / cards_required_total if cards_required_total > 0 else 0.0
                cards_found_unique = len(cards_found_by_name)

                # Score: prioritize completeness, then minimize cost and stores
                score = completeness_by_quantity * 1000 - total_cost * 0.1 - len(stores_used) * 10

                if score > best_score:
                    best_score = score
                    best_solution = solution

            except Exception as e:
                logger.warning(f"Failed to evaluate solution: {str(e)}")
                continue

        return best_solution if best_solution is not None else solutions[0]

    def _evaluate_solution_moead(
        self, individual, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame
    ) -> Tuple[float, float, float, float]:
        """Evaluate solution for MOEA/D with consistent card quantity tracking"""
        try:
            # CLEAR INITIALIZATION: Get required card quantities from wishlist
            cards_required_total = int(user_wishlist_df["quantity"].sum())
            cards_required_by_name = {row["name"]: int(row["quantity"]) for _, row in user_wishlist_df.iterrows()}

            # CLEAR TRACKING: Initialize counters
            stores_used = set()
            total_cost = 0
            quality_scores = []
            cards_found_total = 0
            cards_found_by_name = defaultdict(int)

            for idx in individual:
                if idx not in filtered_listings_df.index:
                    continue

                card = filtered_listings_df.loc[idx]
                card_name = card["name"]

                # Check if we need more of this card
                required_qty = cards_required_by_name.get(card_name, 0)
                found_qty = cards_found_by_name[card_name]

                if found_qty >= required_qty:
                    continue  # Already have enough of this card

                # Count this card
                cards_found_total += 1
                cards_found_by_name[card_name] += 1

                # Use weighted price if available, otherwise use base price
                price = card.get("weighted_price", card.get("price", 1000))
                total_cost += price
                stores_used.add(card["site_name"])

                # Compute quality score
                quality = card.get("quality", "DMG")
                try:
                    normalized_quality = CardQuality.normalize(quality)
                    quality_weight = CardQuality.get_weight(normalized_quality)
                    quality_score = 1 - (quality_weight - 1) / 4  # Normalize to 0-1
                except:
                    quality_score = 0.5  # Default quality score

                quality_scores.append(quality_score)

            # CLEAR CALCULATION: Calculate metrics
            completeness_by_quantity = cards_found_total / cards_required_total if cards_required_total > 0 else 0.0
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
            store_count = len(stores_used)

            # Apply penalties for constraint violations
            if completeness_by_quantity < 1.0:
                incompleteness_penalty = (1 - completeness_by_quantity) * cards_required_total * 100
                total_cost += incompleteness_penalty

            if store_count > self.optimization_config.max_unique_store:
                store_penalty = (store_count - self.optimization_config.max_unique_store) * 1000
                total_cost += store_penalty

            # Return all objectives as minimization (negative for maximization objectives)
            return (
                float(total_cost),  # Minimize cost
                float(-avg_quality),  # Minimize negative quality (maximize quality)
                float(-completeness_by_quantity),  # Minimize negative completeness (maximize completeness)
                float(store_count),  # Minimize store count
            )

        except Exception as e:
            logger.warning(f"Evaluation failed: {str(e)}")
            # Return worst possible values
            return (float("inf"), 0.0, -1.0, float("inf"))

    def _run_moead_optimization(
        self, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame
    ) -> Tuple[Optional[List], Optional[List]]:
        """Main MOEA/D algorithm implementation with consistent card quantity tracking"""

        try:
            # CLEAR INITIALIZATION: Get required card quantities
            cards_required_total = int(user_wishlist_df["quantity"].sum())
            cards_required_unique = len(user_wishlist_df)

            logger.info(
                f"MOEA/D starting with {cards_required_total} total cards needed ({cards_required_unique} unique)"
            )

            # Initialize toolbox
            toolbox = self._initialize_toolbox(filtered_listings_df, user_wishlist_df)

            # Initialize population - one individual per weight vector
            population = []
            logger.info("Initializing population...")

            for i in range(len(self.weight_vectors)):
                try:
                    individual = toolbox.individual()
                    fitness_values = toolbox.evaluate(individual)
                    if not fitness_values or len(fitness_values) != 4:
                        fitness_values = (float("inf"), 0.0, 0.0, float("inf"))
                    individual.fitness.values = fitness_values
                    population.append(individual)
                except Exception as e:
                    logger.warning(f"Failed to create individual {i}: {str(e)}")
                    # Create a fallback individual
                    individual = self._create_fallback_individual(filtered_listings_df, user_wishlist_df)
                    individual.fitness.values = toolbox.evaluate(individual)
                    population.append(individual)

            # Initialize reference point (ideal point)
            reference_point = np.array([float("inf")] * self.n_objectives)

            # External Pareto archive for non-dominated solutions
            pareto_archive = tools.ParetoFront()
            pareto_archive.update(population)

            # Update reference point
            for ind in population:
                for i in range(self.n_objectives):
                    if ind.fitness.values[i] < reference_point[i]:
                        reference_point[i] = ind.fitness.values[i]

            best_complete_solution = None
            best_completeness = 0
            generations_without_improvement = 0

            logger.info("Starting MOEA/D evolution...")

            # Main evolution loop
            for generation in range(self.max_generations):
                try:
                    progress = 0.3 + (generation / self.max_generations) * 0.6
                    self._update_progress(progress, f"Generation {generation + 1}/{self.max_generations}")

                    for i in range(len(self.weight_vectors)):
                        # Select parents from neighborhood
                        parent_indices = random.sample(self.neighborhoods[i], min(2, len(self.neighborhoods[i])))
                        if len(parent_indices) < 2:
                            parent_indices = [i, i]  # Use same individual twice if needed

                        parent1 = population[parent_indices[0]]
                        parent2 = population[parent_indices[1]]

                        # Create offspring through crossover and mutation
                        try:
                            offspring = toolbox.mate(toolbox.clone(parent1), toolbox.clone(parent2))
                            offspring = toolbox.mutate(offspring[0])[0]  # Take first offspring and mutate

                            # Evaluate offspring
                            offspring.fitness.values = toolbox.evaluate(offspring)
                        except Exception as e:
                            logger.warning(f"Failed to create offspring: {str(e)}")
                            continue

                        # Update reference point
                        for j in range(self.n_objectives):
                            if offspring.fitness.values[j] < reference_point[j]:
                                reference_point[j] = offspring.fitness.values[j]

                        # Update neighboring solutions
                        for neighbor_idx in self.neighborhoods[i]:
                            neighbor = population[neighbor_idx]
                            neighbor_weight = self.weight_vectors[neighbor_idx]

                            # Calculate scalar fitness using decomposition method
                            neighbor_scalar = self._calculate_scalar_fitness(
                                neighbor.fitness.values, neighbor_weight, reference_point
                            )
                            offspring_scalar = self._calculate_scalar_fitness(
                                offspring.fitness.values, neighbor_weight, reference_point
                            )

                            # Replace if offspring is better
                            if offspring_scalar < neighbor_scalar:
                                population[neighbor_idx] = toolbox.clone(offspring)

                        # Update Pareto archive
                        pareto_archive.update([offspring])

                        # CLEAR TRACKING: Track best complete solution
                        offspring_completeness = -offspring.fitness.values[2]  # Convert back from minimization
                        if offspring_completeness > best_completeness:
                            best_completeness = offspring_completeness
                            best_complete_solution = toolbox.clone(offspring)
                            generations_without_improvement = 0

                    # CLEAR LOGGING: Log progress with consistent terminology
                    if generation % 20 == 0:
                        complete_solutions = [ind for ind in pareto_archive if -ind.fitness.values[2] >= 0.99]
                        logger.info(f"Gen {generation}: {len(complete_solutions)} complete solutions in archive")
                        logger.info(f"  Best completeness: {best_completeness:.1%}")
                        logger.info(f"  Archive size: {len(pareto_archive)}")

                    # Convergence check
                    generations_without_improvement += 1
                    if generations_without_improvement >= 30:
                        logger.info(f"Converged after {generation} generations without improvement")
                        break

                except Exception as e:
                    logger.warning(f"Error in generation {generation}: {str(e)}")
                    continue

            # Extract results
            try:
                complete_solutions = [list(ind) for ind in pareto_archive if -ind.fitness.values[2] >= 0.99]
                all_solutions = [list(ind) for ind in pareto_archive]

                if complete_solutions:
                    logger.info(f"MOEA/D found {len(complete_solutions)} complete solutions")
                    logger.info(f"  Total solutions in archive: {len(all_solutions)}")
                    return complete_solutions, all_solutions
                elif best_complete_solution:
                    logger.info(f"MOEA/D found best partial solution (completeness: {best_completeness:.1%})")
                    return [list(best_complete_solution)], all_solutions
                else:
                    logger.warning("MOEA/D found no satisfactory solutions")
                    return None, None

            except Exception as e:
                logger.error(f"Failed to extract results: {str(e)}")
                return None, None

        except Exception as e:
            logger.error(f"MOEA/D optimization failed: {str(e)}", exc_info=True)
            return None, None

    def _create_fallback_individual(self, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame):
        """Create a simple fallback individual with consistent length calculation"""
        # CLEAR CALCULATION: Use consistent method to get expected length
        expected_length = int(user_wishlist_df["quantity"].sum())
        individual = []

        for _ in range(expected_length):
            # Simple random selection
            individual.append(random.randint(0, len(filtered_listings_df) - 1))

        individual_class = getattr(creator, self.individual_class_name)
        return individual_class(individual)

    def _calculate_scalar_fitness(
        self, objectives: Tuple[float, ...], weight: np.ndarray, reference_point: np.ndarray
    ) -> float:
        """Calculate scalar fitness using decomposition method"""
        try:
            if self.decomposition_method == "tchebycheff":
                # Tchebycheff approach
                if not objectives or len(objectives) == 0:
                    return float("inf")
                values = [weight[i] * abs(objectives[i] - reference_point[i]) for i in range(len(objectives))]
                return max(values) if values else float("inf")

            elif self.decomposition_method == "weighted_sum":
                # Weighted sum approach
                return sum(weight[i] * objectives[i] for i in range(len(objectives)))

            elif self.decomposition_method == "pbi":
                # Penalty-based boundary intersection
                norm_weight = weight / (np.linalg.norm(weight) + 1e-10)  # Avoid division by zero

                # Calculate d1 (distance along weight vector)
                d1 = abs(sum((objectives[i] - reference_point[i]) * norm_weight[i] for i in range(len(objectives))))

                # Calculate d2 (distance perpendicular to weight vector)
                proj_length = sum((objectives[i] - reference_point[i]) * norm_weight[i] for i in range(len(objectives)))
                d2_squared = sum(
                    (objectives[i] - reference_point[i] - proj_length * norm_weight[i]) ** 2
                    for i in range(len(objectives))
                )
                d2 = math.sqrt(max(0, d2_squared))  # Ensure non-negative

                theta = 5.0  # Penalty parameter
                return d1 + theta * d2

            else:
                # Default to Tchebycheff
                return max(weight[i] * abs(objectives[i] - reference_point[i]) for i in range(len(objectives)))

        except Exception as e:
            logger.warning(f"Error in scalar fitness calculation: {str(e)}")
            # Fallback to simple weighted sum
            return sum(weight[i] * objectives[i] for i in range(len(objectives)))

    def _initialize_toolbox(self, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame):
        """Initialize DEAP toolbox for MOEA/D"""
        toolbox = base.Toolbox()

        # Get the individual class
        individual_class = getattr(creator, self.individual_class_name)

        # Individual initialization
        def create_individual():
            return self._initialize_individual_smart(filtered_listings_df, user_wishlist_df)

        toolbox.register("individual", create_individual)

        # Evaluation function
        def evaluate_individual(individual):
            return self._evaluate_solution_moead(individual, filtered_listings_df, user_wishlist_df)

        toolbox.register("evaluate", evaluate_individual)

        # Genetic operators
        toolbox.register("mate", self._smart_crossover)
        toolbox.register(
            "mutate",
            partial(
                self._smart_mutation,
                filtered_listings_df=filtered_listings_df,
                user_wishlist_df=user_wishlist_df,
            ),
        )
        toolbox.register("clone", lambda ind: individual_class(ind[:]))

        return toolbox

    def _initialize_individual_smart(self, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame):
        """Smart individual initialization for MOEA/D"""
        individual = []
        expected_length = sum(user_wishlist_df["quantity"])
        individual_class = getattr(creator, self.individual_class_name)

        try:
            for _, card in user_wishlist_df.iterrows():
                card_name = card["name"]
                required_quantity = int(card.get("quantity", 1))

                # Find available options for this card
                available_options = filtered_listings_df[filtered_listings_df["name"] == card_name]

                if not available_options.empty:
                    # Simple weighted selection
                    for _ in range(required_quantity):
                        # Weight by inverse price for bias towards cheaper options
                        prices = available_options["price"].values
                        weights = 1.0 / (prices + 0.1)  # Add small value to avoid division by zero
                        weights = weights / weights.sum()  # Normalize

                        selected_idx = np.random.choice(available_options.index, p=weights)
                        individual.append(selected_idx)
                else:
                    # Fallback: random selection
                    for _ in range(required_quantity):
                        individual.append(random.randint(0, len(filtered_listings_df) - 1))

            # Ensure correct length
            if len(individual) != expected_length:
                if len(individual) < expected_length:
                    individual.extend(
                        [
                            random.randint(0, len(filtered_listings_df) - 1)
                            for _ in range(expected_length - len(individual))
                        ]
                    )
                else:
                    individual = individual[:expected_length]

            return individual_class(individual)

        except Exception as e:
            logger.warning(f"Smart initialization failed: {str(e)}, using fallback")
            return self._create_fallback_individual(filtered_listings_df, user_wishlist_df)

    def _smart_crossover(self, ind1, ind2):
        """Enhanced crossover for MOEA/D"""
        if len(ind1) > 2:
            # Uniform crossover with 50% probability
            for i in range(len(ind1)):
                if random.random() < 0.5:
                    ind1[i], ind2[i] = ind2[i], ind1[i]
        return ind1, ind2

    def _smart_mutation(
        self, individual, filtered_listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame, indpb: float = 0.1
    ):
        """Smart mutation for MOEA/D"""
        try:
            for i in range(len(individual)):
                if random.random() < indpb:
                    # Simple random replacement
                    individual[i] = random.randint(0, len(filtered_listings_df) - 1)
        except Exception as e:
            logger.warning(f"Mutation failed: {str(e)}")

        return (individual,)

    def _create_failed_result(self) -> OptimizationResult:
        """Create a failed optimization result"""
        return OptimizationResult(
            best_solution={},
            all_solutions=[],
            algorithm_used="MOEA/D",
            execution_time=self.get_execution_time(),
            iterations=0,
            convergence_metric=1.0,
            performance_stats=self.execution_stats,
        )

    def get_algorithm_name(self) -> str:
        return "MOEA/D"

    def __del__(self):
        """Clean up DEAP classes when optimizer is destroyed"""
        try:
            if hasattr(creator, self.fitness_class_name):
                delattr(creator, self.fitness_class_name)
            if hasattr(creator, self.individual_class_name):
                delattr(creator, self.individual_class_name)
        except:
            pass  # Ignore cleanup errors
