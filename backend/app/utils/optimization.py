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
from app.dto.optimization_dto import CardQuality, QUALITY_MAPPING, QUALITY_WEIGHTS


logger = logging.getLogger(__name__)

# DEAP Setup
creator.create("FitnessMulti", base.Fitness, weights=(-1.0, 1.0, 1.0, -1.0))
creator.create("Individual", list, fitness=creator.FitnessMulti)


class PurchaseOptimizer:
    def __init__(self, filtered_listings_df, user_wishlist_df, config):
        # Update column mapping to match actual DataFrame columns
        self.column_mapping = {
            'name': 'name',
            'site_name': 'site_name',  # Changed from site_name to site
            'price': 'price',
            'quality': 'quality', 
            'quantity': 'quantity'
        }
        
        # Convert input data to DataFrames with standardized column names
        self.filtered_listings_df = self._standardize_dataframe(filtered_listings_df)
        self.user_wishlist_df = pd.DataFrame(user_wishlist_df)
        self.config = config
        
        logger.info("PurchaseOptimizer initialized with config: %s", self.config)
        # Use centralized quality weights
        self.quality_weights = QUALITY_WEIGHTS
        
        self._validate_input_data()

        # Add validation for sites
        unique_sites = filtered_listings_df['site_name'].nunique()
        if unique_sites < config.get('min_store', 1):
            logger.warning(f"Found only {unique_sites} sites, but minimum {config.get('min_store')} required")
            # Adjust min_store if needed
            config['min_store'] = min(unique_sites, config.get('min_store', 1))
            
        logger.info(f"Initializing optimizer with {unique_sites} unique sites")

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
                elif required_col == 'site_name':
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
            'filtered_listings': ['name', 'site_name', 'price', 'quality', 'quantity'],
            'user_wishlist': ['name', 'quantity']
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
            self.filtered_listings_df,
            self.user_wishlist_df,
            self.config["min_store"],
            self.config["find_min_store"],
        )

    def run_nsga_ii_optimization(self, milp_solution=None):
        return self._run_nsga_ii(self.filtered_listings_df, self.user_wishlist_df, milp_solution)

    def run_optimization(self, card_names, config):
        """Run the optimization algorithm based on configuration"""
        try:
            # Debug incoming data
            logger.debug(f"Input DataFrame columns: {self.filtered_listings_df.columns.tolist()}")
            
            # Ensure site column is string type and properly formatted
            self.filtered_listings_df['site_name'] = (
                self.filtered_listings_df['site_name'].astype(str)
            )
            
            # Filter and validate data
            filtered_df = self.filtered_listings_df[
                self.filtered_listings_df["name"].isin(card_names)
            ]
            
            # Debug site data
            logger.info(f"Unique sites: {filtered_df['site_name'].nunique()}")
            logger.debug(f"Site values: {filtered_df['site_name'].unique().tolist()}")

            if filtered_df.empty:
                logger.error("No matching cards found in listings")
                return {"sites_results": [], "iterations": None}

            logger.info(f"Starting optimization with {len(card_names)} cards")
            logger.info(f"Found {filtered_df['site_name'].nunique()} unique sites")
            logger.debug(f"Unique sites: {filtered_df['site_name'].unique().tolist()}")

            # Run the optimization strategy
            try:
                if config["milp_strat"]:
                    logger.info("Running MILP optimization...")
                    results, iterations = self.run_milp_optimization()
                    
                    if results is None:
                        logger.warning("MILP optimization returned no results")
                        return {"sites_results": [], "iterations": None}
                    
                    # Convert results to serializable format
                    if isinstance(results, pd.DataFrame):
                        logger.debug("Converting DataFrame results to records")
                        results = results.to_dict("records")
                    elif isinstance(results, dict):
                        logger.debug("Converting dict results to list")
                        results = [results]
                    elif isinstance(results, list):
                        logger.debug("Processing list results")
                        results = [r.to_dict() if hasattr(r, 'to_dict') else r for r in results]
                    else:
                        logger.error(f"Unexpected results type: {type(results)}")
                        return {"sites_results": [], "iterations": None}

                    final_result = {
                        "sites_results": results,
                        "iterations": iterations if iterations is not None else None
                    }
                    
                    # Validate final result
                    logger.info(f"Final optimization results:")
                    logger.info(f"Number of site results: {len(results)}")
                    if iterations:
                        logger.info(f"Number of iterations: {len(iterations)}")
                    
                    return final_result

            except Exception as e:
                logger.error(f"Optimization strategy error: {str(e)}", exc_info=True)
                raise

        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}", exc_info=True)
            raise

    def get_purchasing_plan(self, solution):
        return [{k: str(v) if isinstance(v, pd.Series) else v 
                 for k, v in plan.items()} 
                for plan in self._extract_purchasing_plan(
            solution, self.filtered_listings_df, self.user_wishlist_df
        )]

    def _run_pulp(self, filtered_listings_df, user_wishlist_df, min_store, find_min_store):
        """Run MILP optimization"""
        try:
            # Validate and clean input data
            filtered_listings_df = filtered_listings_df.copy()
            
            # Ensure site column is string and properly formatted
            filtered_listings_df['site_name'] = filtered_listings_df['site_name'].fillna(
                filtered_listings_df['site_name']
            ).astype(str)
            
            # Debug site data
            logger.debug(f"Site column unique values: {filtered_listings_df['site_name'].unique().tolist()}")
            logger.debug(f"Site column data type: {filtered_listings_df['site_name'].dtype}")

            # Validate input data
            if user_wishlist_df is None or user_wishlist_df.empty:
                logger.error("user_wishlist_df is None or empty")
                return None, None
                
            if filtered_listings_df is None or filtered_listings_df.empty:
                logger.error("filtered_listings_df is None or empty")
                return None, None

            # Ensure unique site IDs are being used
            filtered_listings_df = filtered_listings_df.copy()
            filtered_listings_df['site_name'] = filtered_listings_df['site_name'].combine_first(filtered_listings_df['site_name'])
            
            # Remove duplicates and validate columns
            filtered_listings_df = filtered_listings_df.loc[:, ~filtered_listings_df.columns.duplicated()]
            
            logger.info(f"DataFrame columns after deduplication: {filtered_listings_df.columns.tolist()}")
            logger.info(f"User wishlist columns: {user_wishlist_df.columns.tolist()}")
            logger.info(f"Unique sites before optimization: {filtered_listings_df['site_name'].nunique()}")

            # Get unique values from DataFrame columns correctly
            try:
                unique_cards = user_wishlist_df["name"].unique()
                unique_stores = filtered_listings_df["site_name"].unique()
            except AttributeError as e:
                logger.error(f"Error accessing columns: {e}")
                logger.error(f"user_wishlist_df info: {user_wishlist_df.info()}")
                logger.error(f"filtered_listings_df info: {filtered_listings_df.info()}")
                raise

            logger.info(f"Unique cards: {len(unique_cards)}")
            logger.info(f"Unique stores: {len(unique_stores)}")
            
            total_qty = len(user_wishlist_df)
            high_cost = 10000  # High cost for unavailable card-store combinations

            costs = {}
            for card in unique_cards:
                costs[card] = {}
                for store in unique_stores:
                    card_data = filtered_listings_df[
                        (filtered_listings_df["name"] == card) &
                        (filtered_listings_df["site_name"] == store)
                    ]
                    
                    if not card_data.empty:
                        # Use correct column name for weighted price
                        base_price = card_data["weighted_price"].min()
                        quality = card_data["quality"].iloc[0] if not pd.isna(card_data["quality"].iloc[0]) else "NM"
                        quality_multiplier = self.quality_weights.get(quality, self.quality_weights["NM"])
                        adjusted_price = base_price * quality_multiplier
                        costs[card][store] = adjusted_price if not pd.isna(adjusted_price) else high_cost
                    else:
                        costs[card][store] = high_cost

            all_iterations_results = []
            no_optimal_found = False

            # Validate minimum store requirement
            unique_stores = filtered_listings_df["site_name"].unique()
            if len(unique_stores) < min_store:
                logger.warning(f"Not enough stores available ({len(unique_stores)}) for minimum requirement ({min_store})")
                min_store = len(unique_stores)  # Adjust min_store to available stores
                
            logger.info(f"Running optimization with {len(unique_stores)} stores and minimum requirement of {min_store}")

            if not find_min_store:
                prob, buy_vars = PurchaseOptimizer._setup_prob(
                    costs, unique_cards, unique_stores, user_wishlist_df, min_store
                )
                if pulp.LpStatus[prob.status] != "Optimal":
                    logger.warning("Solver did not find an optimal solution.")
                    return None
                all_iterations_results = PurchaseOptimizer._process_result(
                    buy_vars, costs, False, total_qty, filtered_listings_df
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
                        user_wishlist_df,
                        current_min,
                    )

                    if pulp.LpStatus[prob.status] != "Optimal":
                        logger.warning("Solver did not find an optimal solution.")
                        break

                    iteration_results = PurchaseOptimizer._process_result(
                        buy_vars, costs, True, total_qty, filtered_listings_df
                    )
                    all_iterations_results.append(iteration_results)

                    logger.info(
                        f"Iteration [{iteration}]: Total price {iteration_results['total_price']:.2f}$ {int(iteration_results['nbr_card_in_solution'])}/{total_qty}"
                    )

                    iteration += 1
                    current_min -= 1

                if not all_iterations_results:
                    return None

                least_expensive_iteration = min(
                    all_iterations_results, key=lambda x: x["total_price"]
                )
                logger.info(
                    f"Best Iteration is with {least_expensive_iteration['Number_store']} stores with a total price of: {least_expensive_iteration['Total_price']:.2f}$"
                )
                logger.info(
                    f"Using these 'stores: #cards': {least_expensive_iteration['list_stores']}"
                )

                return (
                    least_expensive_iteration["sorted_results_df"],
                    all_iterations_results,
                )
        except Exception as e:
            logger.error("_run_pulp: %s", str(e))
            logger.error("DataFrame columns: %s", filtered_listings_df.columns.tolist())
            raise


    @staticmethod
    def _setup_prob(costs, unique_cards, unique_stores, user_wishlist, min_store):
        # Add validation for store count
        if len(unique_stores) < min_store:
            logger.warning(f"Adjusting min_store from {min_store} to {len(unique_stores)} due to available stores")
            min_store = len(unique_stores)
            
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
            required_quantity = user_wishlist[user_wishlist["name"]
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
    def _process_result(buy_vars, costs, limited_output, total_qty, filtered_listings_df):
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
                        original_index = filtered_listings_df[
                            (filtered_listings_df["name"] == card)
                            & (filtered_listings_df["site_name"] == store)
                        ].index[0]
                        original_card = filtered_listings_df.loc[original_index]

                        results.append(
                            {
                                "original_Index": original_index,
                                "original_Card": original_card,
                                "name": card,
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
        sorted_results_df = results_df.sort_values(by=["store", "name"])
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

        # Convert DataFrame to dict before returning
        return_value = {
            "nbr_card_in_solution": total_card_nbr,
            "total_price": float(Total_price),  # Ensure float
            "number_store": int(num_stores_used),  # Ensure int
            "list_stores": store_usage_str,
            "sorted_results_df": sorted_results_df
        }

        return return_value

    @staticmethod
    def _run_nsga_ii(filtered_listings_df, user_wishlist_df, milp_solution=None):
        toolbox = PurchaseOptimizer._initialize_toolbox(
            filtered_listings_df, user_wishlist_df)

        NGEN, MU, CXPB, MUTPB = 1000, 3000, 0.5, 0.2
        ELITISM_SIZE = int(0.1 * MU)

        if milp_solution:
            milp_individual = PurchaseOptimizer._milp_solution_to_individual(
                milp_solution
            )
            pop = PurchaseOptimizer._initialize_population_with_milp(
                MU, filtered_listings_df, user_wishlist_df, milp_individual
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
    def _initialize_toolbox(filtered_listings_df, user_wishlist_df):
        toolbox = base.Toolbox()
        toolbox.register("attr_idx", random.randint,
                         0, len(filtered_listings_df) - 1)
        toolbox.register(
            "individual",
            tools.initRepeat,
            creator.Individual,
            toolbox.attr_idx,
            n=sum(user_wishlist_df["quantity"]),
        )
        toolbox.register("population", tools.initRepeat,
                         list, toolbox.individual)
        toolbox.register(
            "evaluate",
            PurchaseOptimizer._evaluate_solution_wrapper(
                filtered_listings_df, user_wishlist_df),
        )
        toolbox.register("mate", PurchaseOptimizer._custom_crossover)
        toolbox.register(
            "mutate",
            partial(
                PurchaseOptimizer._custom_mutation,
                filtered_listings_df=filtered_listings_df,
                user_wishlist_df=user_wishlist_df,
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
    def _custom_mutation(individual, filtered_listings_df, user_wishlist_df, indpb=0.05):
        for i in range(len(individual)):
            if random.random() < indpb:
                mutation_index = random.randrange(len(individual))
                card_name = user_wishlist_df.iloc[mutation_index]["name"]
                available_options = filtered_listings_df[
                    filtered_listings_df["name"] == card_name
                ]
                if not available_options.empty:
                    selected_option = available_options.sample(n=1)
                    individual[mutation_index] = selected_option.index.item()
        return (individual,)

    @staticmethod
    def _evaluate_solution_wrapper(filtered_listings_df, user_wishlist_df):
        def evaluate_solution(individual):
            total_cost = 0
            total_quality_score = 0
            stores = set()
            card_counters = {
                row["name"]: row["quantity"] for _, row in user_wishlist_df.iterrows()
            }
            card_availability = {row["name"]: 0 for _, row in user_wishlist_df.iterrows()}
            language_penalty = 999
            # Use centralized quality weights
            quality_weights = QUALITY_WEIGHTS

            all_cards_present = all(
                card_counters[getattr(card_row, "Name")] > 0
                for card_row in filtered_listings_df.itertuples()
            )
            if not all_cards_present:
                return (float("inf"),)

            for idx in individual:
                if idx not in filtered_listings_df.index:
                    logger.warning(f"Invalid index: {idx}")
                    continue
                card_row = filtered_listings_df.loc[idx]
                card_name = card_row["name"]
                user_wishlist_card = user_wishlist_df[user_wishlist_df["name"] == card_name].iloc[0]
                
                # Add quality matching penalty
                requested_quality = user_wishlist_card.get("quality", "NM")
                actual_quality = card_row.get("Quality", "NM")
                quality_mismatch_penalty = (
                    quality_weights[requested_quality] - 
                    quality_weights.get(actual_quality, quality_weights["DMG"])
                ) * 10  # Adjust penalty weight as needed

                if card_counters[card_name] > 0:
                    card_counters[card_name] -= 1
                    card_availability[card_name] += card_row["quantity"]

                    card_price = card_row["Price"]
                    if card_row["language"] != "English":
                        card_price *= language_penalty
                    total_cost += card_price + quality_mismatch_penalty

                    total_quality_score += quality_weights.get(
                        card_row["quality"], 0)
                    stores.add(card_row["site_name"])

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
    def _extract_purchasing_plan(solution, filtered_listings_df, user_wishlist_df):
        purchasing_plan = []
        
        # Handle different solution formats
        if isinstance(solution, dict):
            solutions_to_process = [solution]
        elif isinstance(solution, (list, tuple)):
            # Convert indices to actual card data
            solutions_to_process = []
            for idx in solution:
                if isinstance(idx, int) and idx in filtered_listings_df.index:
                    solutions_to_process.append(filtered_listings_df.loc[idx].to_dict())
                elif isinstance(idx, (pd.Series, dict)):
                    solutions_to_process.append(idx)
        else:
            logger.warning(f"Unexpected solution type: {type(solution)}")
            return []

        for item in solutions_to_process:
            try:
                # Ensure we have a dictionary to work with
                card_row = item if isinstance(item, dict) else (
                    item.to_dict() if isinstance(item, pd.Series) else None
                )
                
                if not card_row:
                    logger.warning(f"Invalid card data format: {type(item)}")
                    continue

                card_name = card_row.get("name")
                if not card_name:
                    logger.warning(f"Missing card name in data: {card_row}")
                    continue

                if card_name in user_wishlist_df["name"].values:
                    user_wishlist_row = user_wishlist_df[user_wishlist_df["name"] == card_name].iloc[0]
                    required_quality = user_wishlist_row.get("quality", "NM")
                    card_quality = card_row.get("quality", "NM")
                    
                    # Only include cards that meet or exceed the required quality
                    quality_weights = QUALITY_WEIGHTS  # Use the imported quality weights
                    quality_check = (required_quality == card_quality or 
                                   quality_weights[card_quality] <= 
                                   quality_weights[required_quality])
                    
                    if quality_check:
                        required_quantity = user_wishlist_row["quantity"]
                        available_quantity = min(
                            int(card_row.get("quantity", 0)), 
                            int(required_quantity)
                        )

                        if available_quantity > 0:
                            price = float(card_row.get("price", 0))
                            purchase_details = {
                                "name": card_name,
                                "quantity": available_quantity,
                                "site": card_row.get("site"),
                                "quality": card_quality,
                                "price": price,
                                "total_price": price * available_quantity,
                                "quality_match": required_quality == card_quality
                            }
                            purchasing_plan.append(purchase_details)

                            # Update user wishlist
                            mask = user_wishlist_df["name"] == card_name
                            user_wishlist_df.loc[mask, "quantity"] -= available_quantity

            except Exception as e:
                logger.warning(f"Error processing card {card_row if 'card_row' in locals() else 'unknown'}: {str(e)}")
                continue

        # Remove entries with zero quantity left
        user_wishlist_df = user_wishlist_df[user_wishlist_df["quantity"] > 0]

        return purchasing_plan

    @staticmethod
    def _initialize_population_with_milp(n, filtered_listings_df, user_wishlist_df, milp_solution):
        population = [
            PurchaseOptimizer._initialize_individual(filtered_listings_df, user_wishlist_df)
            for _ in range(n - 1)
        ]
        milp_individual = PurchaseOptimizer._milp_solution_to_individual(
            milp_solution)
        population.insert(0, milp_individual)
        return population

    @staticmethod
    def _initialize_individual(filtered_listings_df, user_wishlist_df):
        individual = []
        for _, card in user_wishlist_df.iterrows():
            available_options = filtered_listings_df[filtered_listings_df["name"]
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