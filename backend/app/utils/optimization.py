# backend/app/utils/optimization.py
import logging
import random
from functools import partial

import pandas as pd
import pulp
from deap import algorithms, base, creator, tools

from app.extensions import db
from app.models.scan import ScanResult
from mtgsdk import card
from app.dto.optimization_dto import CardQuality


logger = logging.getLogger(__name__)

# DEAP Setup
creator.create("FitnessMulti", base.Fitness, weights=(-1.0, 1.0, 1.0, -1.0))
creator.create("Individual", list, fitness=creator.FitnessMulti)


class PurchaseOptimizer:
    def __init__(self, card_details_df, buylist_df, config):
        # Initialize with standardized column names using lowercase
        self.column_mapping = {
            'name': 'name',
            'site_name': 'site',
            'price': 'price',
            'quality': 'quality', 
            'quantity': 'quantity'
        }
        
        # Convert input data to DataFrames with standardized column names
        self.card_details_df = self._standardize_dataframe(pd.DataFrame(card_details_df))
        self.buylist_df = pd.DataFrame(buylist_df)
        self.config = config
        
        logger.info("PurchaseOptimizer initialized with config: %s", self.config)
        self.quality_weights = {
            "NM": 1.0,
            "LP": 1.2,
            "MP": 1.5,
            "HP": 2.0,
            "DMG": 3.0
        }
        
        self._validate_input_data()

    def _standardize_dataframe(self, df):
        """Standardize DataFrame column names and validate quality values"""
        df = df.copy()
        
        # Rename columns based on mapping
        df = df.rename(columns=self.column_mapping)
        
        # Ensure all required columns exist
        for required_col in self.column_mapping.values():
            if (required_col not in df.columns):
                logger.warning(f"Missing column {required_col}, creating with default values")
                if required_col in ['price', 'quantity']:
                    df[required_col] = 0
                elif required_col == 'quality':
                    df[required_col] = 'NM'
                elif required_col == 'site':
                    df[required_col] = df['site_id'].astype(str)
                else:
                    df[required_col] = ''
        
        # Validate and normalize quality values
        if 'quality' in df.columns:
            try:
                df = CardQuality.validate_and_update_qualities(
                    df, 
                    quality_column='quality',
                    interactive=False  # Set to True if you want interactive prompts
                )
            except Exception as e:
                logger.warning(f"Error normalizing qualities: {e}")

        return df

    def _validate_input_data(self):
        """Validate input data structure and content"""
        required_columns = {
            'card_details': ['name', 'site', 'price', 'quality', 'quantity'],
            'buylist': ['name', 'quantity']
        }

        for df_name, columns in required_columns.items():
            df = getattr(self, f"{df_name}_df")
            missing_cols = [col for col in columns if col not in df.columns]
            if missing_cols:
                logger.error(f"DataFrame {df_name} columns: {df.columns.tolist()}")
                logger.error(f"Missing columns in {df_name}: {missing_cols}")
                raise ValueError(f"Missing required columns in {df_name}: {missing_cols}")
            
            # Validate data types
            if df_name == 'card_details':
                if not pd.to_numeric(df['price'], errors='coerce').notnull().all():
                    raise ValueError("Price column contains non-numeric values")
                if not pd.to_numeric(df['quantity'], errors='coerce').notnull().all():
                    raise ValueError("Quantity column contains non-numeric values")

    def run_milp_optimization(self):
        return self._run_pulp(
            self.card_details_df,
            self.buylist_df,
            self.config["min_store"],
            self.config["find_min_store"],
        )

    def run_nsga_ii_optimization(self, milp_solution=None):
        return self._run_nsga_ii(self.card_details_df, self.buylist_df, milp_solution)

    def run_optimization(self, card_names, sites, config):
        """Run the optimization algorithm based on configuration"""
        try:
            # Filter card_details_df to only include cards in the buylist
            self.card_details_df = self.card_details_df[
                self.card_details_df["name"].isin(card_names)
            ]

            # Run the optimization strategy
            if config["milp_strat"]:
                results, iterations = self.run_milp_optimization()
            elif config["nsga_algo_strat"]:
                results = self.run_nsga_ii_optimization()
            elif config["hybrid_strat"]:
                milp_solution, _ = self.run_milp_optimization()
                results = self.run_nsga_ii_optimization(milp_solution)
            else:
                raise ValueError("No valid optimization strategy specified in config")

            # Process results
            if isinstance(results, pd.DataFrame):
                sites_results = results.to_dict("records")
            else:
                sites_results = [self.get_purchasing_plan(solution) for solution in results]

            return {
                "sites_results": sites_results,
                "iterations": iterations if "iterations" in locals() else None,
            }

        except Exception as e:
            logger.error("Optimization failed: %s", str(e))
            raise

    def get_purchasing_plan(self, solution):
        return self._extract_purchasing_plan(
            solution, self.card_details_df, self.buylist_df
        )

    def _run_pulp(
        self, standardized_cards_df, available_cards_to_buy_df, min_store, find_min_store
    ):
        unique_cards = available_cards_to_buy_df["name"].unique()
        unique_stores = standardized_cards_df["Site"].unique()
        total_qty = len(available_cards_to_buy_df)

        high_cost = 10000  # High cost for unavailable card-store combinations

        costs = {}
        for card in unique_cards:
            costs[card] = {}
            for store in unique_stores:
                card_data = standardized_cards_df[
                    (standardized_cards_df["name"] == card) &
                    (standardized_cards_df["Site"] == store)
                ]
                
                if not card_data.empty:
                    base_price = card_data["Weighted_Price"].min()
                    quality = card_data["quality"].iloc[0] if not pd.isna(card_data["quality"].iloc[0]) else "NM"
                    quality_multiplier = self.quality_weights.get(quality, self.quality_weights["NM"])
                    adjusted_price = base_price * quality_multiplier
                    costs[card][store] = adjusted_price if not pd.isna(adjusted_price) else high_cost
                else:
                    costs[card][store] = high_cost

        all_iterations_results = []
        no_optimal_found = False

        if not find_min_store:
            prob, buy_vars = PurchaseOptimizer._setup_prob(
                costs, unique_cards, unique_stores, available_cards_to_buy_df, min_store
            )
            if pulp.LpStatus[prob.status] != "Optimal":
                logger.warning("Solver did not find an optimal solution.")
                return None
            all_iterations_results = PurchaseOptimizer._process_result(
                buy_vars, costs, False, total_qty, standardized_cards_df
            )
            return all_iterations_results["sorted_results_df"], None
        else:
            logger.info("Starting iterative algorithm")
            current_min = min_store
            iteration = 1
            while current_min >= 1:
                logger.info(
                    f"Iteration [{iteration}]: Current number of diff. stores: {current_min}"
                )
                prob, buy_vars = PurchaseOptimizer._setup_prob(
                    costs,
                    unique_cards,
                    unique_stores,
                    available_cards_to_buy_df,
                    current_min,
                )

                if pulp.LpStatus[prob.status] != "Optimal":
                    logger.warning("Solver did not find an optimal solution.")
                    break

                iteration_results = PurchaseOptimizer._process_result(
                    buy_vars, costs, True, total_qty, standardized_cards_df
                )
                all_iterations_results.append(iteration_results)

                logger.info(
                    f"Iteration [{iteration}]: Total price {iteration_results['Total_price']:.2f}$ {int(iteration_results['nbr_card_in_solution'])}/{total_qty}"
                )

                iteration += 1
                current_min -= 1

            if not all_iterations_results:
                return None

            least_expensive_iteration = min(
                all_iterations_results, key=lambda x: x["Total_price"]
            )
            logger.info(
                f"Best Iteration is with {least_expensive_iteration['Number_store']} stores with a total price of: {least_expensive_iteration['Total_price']:.2f}$"
            )
            logger.info(
                f"Using these 'stores: #cards': {least_expensive_iteration['List_stores']}"
            )

            return (
                least_expensive_iteration["sorted_results_df"],
                all_iterations_results,
            )

    @staticmethod
    def _setup_prob(costs, unique_cards, unique_stores, buylist, min_store):
        prob = pulp.LpProblem("MTGCardOptimization", pulp.LpMinimize)
        buy_vars = pulp.LpVariable.dicts(
            "Buy", (unique_cards, unique_stores), 0, 1, pulp.LpBinary
        )
        store_vars = pulp.LpVariable.dicts(
            "Store", unique_stores, 0, 1, pulp.LpBinary)

        prob += pulp.lpSum(
            [
                buy_vars[card][store] * costs[card][store]
                for card in unique_cards
                for store in unique_stores
            ]
        )

        for card in unique_cards:
            required_quantity = buylist[buylist["name"]
                                        == card]["quantity"].iloc[0]
            prob += (
                pulp.lpSum([buy_vars[card][store] for store in unique_stores])
                == required_quantity
            )

        for store in unique_stores:
            prob += store_vars[store] >= pulp.lpSum(
                buy_vars[card][store] for card in unique_cards
            ) / len(unique_cards)

        prob += pulp.lpSum(store_vars[store]
                           for store in unique_stores) <= min_store
        prob.solve(pulp.PULP_CBC_CMD(msg=False))

        return prob, buy_vars

    @staticmethod
    def _process_result(buy_vars, costs, limited_output, total_qty, card_details_df):
        Total_price = 0.0
        results = []
        total_card_nbr = 0

        for card, store_dict in buy_vars.items():
            for store, var in store_dict.items():
                quantity = var.value()
                if quantity > 0:
                    price_per_unit = costs[card][store]
                    card_store_total_price = quantity * price_per_unit

                    if price_per_unit != 10000:
                        Total_price += card_store_total_price
                        total_card_nbr += quantity
                        original_index = card_details_df[
                            (card_details_df["name"] == card)
                            & (card_details_df["site"] == store)
                        ].index[0]
                        original_card = card_details_df.loc[original_index]

                        results.append(
                            {
                                "original_Index": original_index,
                                "original_Card": original_card,
                                "card": card,
                                "store": store,
                                "quantity": quantity,
                                "price": price_per_unit,
                                "total price": card_store_total_price,
                            }
                        )

                    if not limited_output:
                        logger.info(
                            f"{'Cannot Buy' if price_per_unit == 10000 else 'Buy'} {quantity} x {card} from {store if price_per_unit != 10000 else 'any stores'} at a price of ${price_per_unit} each, totalizing ${card_store_total_price}"
                        )

        results_df = pd.DataFrame(results)
        sorted_results_df = results_df.sort_values(by=["store", "card"])
        sorted_results_df.reset_index(drop=True, inplace=True)

        num_stores_used = results_df["store"].nunique()
        store_usage_counts = sorted_results_df[sorted_results_df["price"] != 10000][
            "store"
        ].value_counts()
        store_usage_str = ", ".join(
            [f"{store}: {count}" for store, count in store_usage_counts.items()]
        )

        if not limited_output:
            logger.info(
                f"Minimum number of different sites to order from: {num_stores_used}"
            )
            logger.info(f"Sites to order from: {store_usage_str}")
            logger.info(f"Total price of all purchases ${Total_price:.2f}")
            logger.info(
                f"Total number of cards purchased: {total_card_nbr}/{total_qty}"
            )

        return {
            "nbr_card_in_solution": total_card_nbr,
            "Total_price": Total_price,
            "Number_store": num_stores_used,
            "List_stores": store_usage_str,
            "sorted_results_df": sorted_results_df,
        }

    @staticmethod
    def _run_nsga_ii(card_details_df, buylist, milp_solution=None):
        toolbox = PurchaseOptimizer._initialize_toolbox(
            card_details_df, buylist)

        NGEN, MU, CXPB, MUTPB = 1000, 3000, 0.5, 0.2
        ELITISM_SIZE = int(0.1 * MU)

        if milp_solution:
            milp_individual = PurchaseOptimizer._milp_solution_to_individual(
                milp_solution
            )
            pop = PurchaseOptimizer._initialize_population_with_milp(
                MU, card_details_df, buylist, milp_individual
            )
        else:
            pop = toolbox.population(n=MU)

        fitnesses = map(toolbox.evaluate, pop)
        for ind, fit in zip(pop, fitnesses):
            ind.fitness.values = fit

        pareto_front = tools.ParetoFront()

        convergence_threshold = 0.01
        num_generations_threshold = 10
        best_fitness_so_far = float("inf")
        generations_without_improvement = 0

        for gen in range(NGEN):
            offspring = algorithms.varAnd(pop, toolbox, CXPB, MUTPB)
            fitnesses = map(toolbox.evaluate, offspring)
            for ind, fit in zip(offspring, fitnesses):
                ind.fitness.values = fit

            pop = toolbox.select(pop + offspring, MU)
            pareto_front.update(pop)

            current_best_fitness = tools.selBest(pop, 1)[0].fitness.values[0]
            if (
                best_fitness_so_far - current_best_fitness
            ) / best_fitness_so_far > convergence_threshold:
                best_fitness_so_far = current_best_fitness
                generations_without_improvement = 0
            else:
                generations_without_improvement += 1

            if generations_without_improvement >= num_generations_threshold:
                logger.info(f"Convergence reached after {gen} generations.")
                break

        return pareto_front

    @staticmethod
    def _initialize_toolbox(card_details_df, buylist):
        toolbox = base.Toolbox()
        toolbox.register("attr_idx", random.randint,
                         0, len(card_details_df) - 1)
        toolbox.register(
            "individual",
            tools.initRepeat,
            creator.Individual,
            toolbox.attr_idx,
            n=sum(buylist["quantity"]),
        )
        toolbox.register("population", tools.initRepeat,
                         list, toolbox.individual)
        toolbox.register(
            "evaluate",
            PurchaseOptimizer._evaluate_solution_wrapper(
                card_details_df, buylist),
        )
        toolbox.register("mate", PurchaseOptimizer._custom_crossover)
        toolbox.register(
            "mutate",
            partial(
                PurchaseOptimizer._custom_mutation,
                card_details_df=card_details_df,
                buylist=buylist,
            ),
        )
        toolbox.register("select", tools.selNSGA2)
        return toolbox

    @staticmethod
    def _custom_crossover(ind1, ind2):
        for i in range(len(ind1)):
            if random.random() < 0.5:
                ind1[i], ind2[i] = ind2[i], ind1[i]
        return ind1, ind2

    @staticmethod
    def _custom_mutation(individual, card_details_df, buylist, indpb=0.05):
        for i in range(len(individual)):
            if random.random() < indpb:
                mutation_index = random.randrange(len(individual))
                card_name = buylist.iloc[mutation_index]["name"]
                available_options = card_details_df[
                    card_details_df["name"] == card_name
                ]
                if not available_options.empty:
                    selected_option = available_options.sample(n=1)
                    individual[mutation_index] = selected_option.index.item()
        return (individual,)

    @staticmethod
    def _evaluate_solution_wrapper(card_details_df, buylist):
        def evaluate_solution(individual):
            total_cost = 0
            total_quality_score = 0
            stores = set()
            card_counters = {
                row["name"]: row["quantity"] for _, row in buylist.iterrows()
            }
            card_availability = {row["name"]                                 : 0 for _, row in buylist.iterrows()}
            language_penalty = 999
            quality_weights = {"NM": 9, "LP": 7, "MP": 3, "HP": 1, "DMG": 0}

            all_cards_present = all(
                card_counters[getattr(card_row, "Name")] > 0
                for card_row in card_details_df.itertuples()
            )
            if not all_cards_present:
                return (float("inf"),)

            for idx in individual:
                if idx not in card_details_df.index:
                    logger.warning(f"Invalid index: {idx}")
                    continue
                card_row = card_details_df.loc[idx]
                card_name = card_row["name"]
                buylist_card = buylist[buylist["name"] == card_name].iloc[0]
                
                # Add quality matching penalty
                requested_quality = buylist_card.get("quality", "NM")
                actual_quality = card_row.get("Quality", "NM")
                quality_mismatch_penalty = (
                    quality_weights[requested_quality] - 
                    quality_weights.get(actual_quality, quality_weights["DMG"])
                ) * 10  # Adjust penalty weight as needed

                if card_counters[card_name] > 0:
                    card_counters[card_name] -= 1
                    card_availability[card_name] += card_row["quantity"]

                    card_price = card_row["Price"]
                    if card_row["Language"] != "English":
                        card_price *= language_penalty
                    total_cost += card_price + quality_mismatch_penalty

                    total_quality_score += quality_weights.get(
                        card_row["quality"], 0)
                    stores.add(card_row["Site"])

            missing_cards_penalty = 10000 * sum(
                count for count in card_counters.values() if count > 0
            )
            store_diversity_penalty = 100 * (len(stores) - 1)

            card_quality = total_quality_score / \
                len(individual) if individual else 0
            all_available = all(
                card_availability[name] >= qty for name, qty in card_counters.items()
            )
            availability_score = 1 if all_available else 0
            num_stores = len(stores)

            return (
                total_cost + missing_cards_penalty + store_diversity_penalty,
                -card_quality,
                -availability_score,
                num_stores,
            )

        return evaluate_solution

    @staticmethod
    def _extract_purchasing_plan(solution, card_details_df, buylist):
        purchasing_plan = []
        for idx in solution:
            if idx not in card_details_df.index:
                logger.warning("Invalid index: %d", idx)
                continue
            card_row = card_details_df.loc[idx]
            card_name = card_row["name"]

            if card_name in buylist["name"].values:
                buylist_row = buylist[buylist["name"] == card_name].iloc[0]
                required_quality = buylist_row.get("quality", "NM")
                card_quality = card_row.get("quality", "NM")
                
                # Only include cards that meet or exceed the required quality
                if (required_quality == card_quality or 
                    PurchaseOptimizer.quality_weights[card_quality] <= 
                    PurchaseOptimizer.quality_weights[required_quality]):
                    required_quantity = buylist_row["quantity"]

                    if required_quantity > 0:
                        available_quantity = min(
                            card_row["quantity"], required_quantity)
                        purchase_details = {
                            "name": card_name,
                            "quantity": available_quantity,
                            "site": card_row["site"],
                            "quality": card_row["quality"],
                            "price": card_row["price"],
                            "total price": card_row["price"] * available_quantity,
                        }
                        purchase_details["quality_match"] = required_quality == card_quality
                        purchasing_plan.append(purchase_details)

                        # Update buylist
                        buylist.loc[
                            buylist["name"] == card_name, "quantity"
                        ] -= available_quantity

        # Remove entries with zero quantity left
        buylist = buylist[buylist["quantity"] > 0]

        return purchasing_plan

    @staticmethod
    def _initialize_population_with_milp(n, card_details_df, buylist, milp_solution):
        population = [
            PurchaseOptimizer._initialize_individual(card_details_df, buylist)
            for _ in range(n - 1)
        ]
        milp_individual = PurchaseOptimizer._milp_solution_to_individual(
            milp_solution)
        population.insert(0, milp_individual)
        return population

    @staticmethod
    def _initialize_individual(card_details_df, buylist):
        individual = []
        for _, card in buylist.iterrows():
            available_options = card_details_df[card_details_df["name"]
                                                == card["name"]]
            if not available_options.empty:
                selected_option = available_options.sample(n=1)
                individual.append(selected_option.index.item())
            else:
                logger.warning(
                    "Card %s not available in any store!", card["name"])
        return creator.Individual(individual)

    @staticmethod
    def _milp_solution_to_individual(milp_solution):
        return creator.Individual(milp_solution)