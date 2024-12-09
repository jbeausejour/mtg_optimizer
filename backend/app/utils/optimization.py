from collections import defaultdict
import logging
import random
from functools import partial
import numpy as np
import pandas as pd
import pulp
from deap import algorithms, base, creator, tools
from app.constants import CardQuality, QUALITY_WEIGHTS


logger = logging.getLogger(__name__)

# DEAP Setup
creator.create("FitnessMulti", base.Fitness, weights=(
    -1.0,  # Minimize cost
    1.0,   # Maximize quality
    10.0,  # Heavily prioritize availability
    -0.1   # Slightly penalize store count
))
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
        if filtered_listings_df.empty or user_wishlist_df.empty:
            raise ValueError("Empty input dataframes")

        if not all(col in filtered_listings_df.columns for col in self.column_mapping.values()):
            raise ValueError(f"Missing required columns: {self.column_mapping.values()}")
        
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
                    quality_column='quality'
                )
            except Exception as e:
                logger.warning(f"Error normalizing qualities: {e}")

        return df

    def _validate_input_data(self):
        """Validate input data structure and content"""
        required_columns = {
            'filtered_listings': ['name', 'site_name', 'price', 'quality', 'quantity'],
            'user_wishlist': ['name', 'quantity', 'min_quality']  # Ensure min_quality is included
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
        try:
            final_result = None
            # Debug incoming data
            logger.debug(f"Input DataFrame columns: {self.filtered_listings_df.columns.tolist()}")

            self.filtered_listings_df['site_name'] = self.filtered_listings_df['site_name'].astype(str)
            self.filtered_listings_df = self.filtered_listings_df[self.filtered_listings_df["name"].isin(card_names)]

            if self.filtered_listings_df.empty:
                logger.error("No matching cards found in listings")
                return {"best_solution": [], "iterations": None}

            # Add logging for unique available cards
            available_cards = sorted(self.filtered_listings_df['name'].unique())
            logger.info(f"Available cards ({len(available_cards)}): {available_cards}")

            logger.info(f"Starting optimization with {len(card_names)} cards")
            logger.info(f"Found {self.filtered_listings_df['site_name'].nunique()} unique sites")
            logger.info(f"Unique sites: {self.filtered_listings_df['site_name'].unique().tolist()}")

            if config["milp_strat"] or config["hybrid_strat"]:
                logger.info("Running MILP optimization...")
                best_solution, all_milp_solutions = self.run_milp_optimization()
                self.filtered_listings_df = self._cleanup_temporary_columns(df=self.filtered_listings_df)

                if best_solution is None:
                    logger.warning("MILP optimization returned no results")
                    return {"best_solution": [], "iterations": None}

                # Convert DataFrame to records for serialization
                best_solution_records = best_solution.to_dict('records') if isinstance(best_solution, pd.DataFrame) else best_solution
                
                # Add set_code and set_name only to records missing them
                for record in best_solution_records:
                    if 'set_code' not in record or not record['set_code']:
                        matching_listings = self.filtered_listings_df[
                            (self.filtered_listings_df['name'] == record['name']) &
                            (self.filtered_listings_df['site_name'] == record['site_name']) &
                            (self.filtered_listings_df['price'] == record['price'])
                        ]
                        
                        if not matching_listings.empty:
                            record['set_code'] = matching_listings.iloc[0]['set_code']
                            record['set_name'] = matching_listings.iloc[0]['set_name']
                        else:
                            logger.warning(f"No matching listing found for {record['name']} at {record['site_name']}")
                            record['set_code'] = ''
                            record['set_name'] = ''

                # Format iterations to be serializable
                formatted_iterations = []
                if all_milp_solutions:
                    for solution in all_milp_solutions:
                        iteration_copy = solution.copy()
                        if isinstance(solution['sorted_results_df'], pd.DataFrame):
                            results_records = solution['sorted_results_df'].to_dict('records')
                            # Add set information only to records missing them
                            for record in results_records:
                                if 'set_code' not in record or not record['set_code']:
                                    matching_listings = self.filtered_listings_df[
                                        (self.filtered_listings_df['name'] == record['name']) &
                                        (self.filtered_listings_df['site_name'] == record['site_name']) &
                                        (self.filtered_listings_df['price'] == record['price'])
                                    ]
                                    if not matching_listings.empty:
                                        record['set_code'] = matching_listings.iloc[0]['set_code']
                                        record['set_name'] = matching_listings.iloc[0]['set_name']
                                    else:
                                        record['set_code'] = ''
                                        record['set_name'] = ''
                            iteration_copy['sorted_results_df'] = results_records
                        formatted_iterations.append(iteration_copy)

                final_result = {
                    "best_solution": best_solution_records,
                    "iterations": formatted_iterations
                }

            if config["nsga_strat"] or config["hybrid_strat"]:
                logger.info("Running NSGA-II optimization...")

                # Convert MILP results to milp_solution
                milp_solution = []
                # Run the optimization algorithm
                if config["hybrid_strat"]:
                    expected_length = sum(self.user_wishlist_df['quantity'])
                    logger.info(f"Hybrid optimization preparation...")
                    # Create a unique identifier in card_details_df
                    self.filtered_listings_df['Identifier'] = self.filtered_listings_df.apply(lambda row: f"{row['name']}_{row['site_name']}_{row['price']}", axis=1)

                    # Create a mapping from the unique identifier to index
                    identifier_to_index = {identifier: idx for idx, identifier in self.filtered_listings_df['Identifier'].items()}

                    if isinstance(final_result.get('best_solution'), list):
                        missing_cards = []
                        for row in final_result['best_solution']:
                            identifier = f"{row['name']}_{row['site_name']}_{row['price']}"
                            if identifier in identifier_to_index:
                                idx = identifier_to_index[identifier]
                                milp_solution.append(idx)
                            else:
                                missing_cards.append(row['name'])
                                alternative = self._find_alternative_listing(row['name'], self.filtered_listings_df)
                                if alternative is not None:
                                    milp_solution.append(alternative)
                                logger.info(f"Combination {identifier} not found in card_details_df.")
                        if len(milp_solution) != expected_length:
                            logger.warning(f"MILP solution incomplete: {len(milp_solution)}/{expected_length} cards. Missing: {missing_cards}")
                    else:
                        logger.warning("best_solution is not a list.")

                    # Drop the 'Identifier' column as it's no longer needed
                    self.filtered_listings_df = self.filtered_listings_df.drop(columns=['Identifier'])
                    
                    logger.info(f"Hybrid optimization preparation complte.")

                # Run NSGA-II without the MILP solution
                pareto_front = self.run_nsga_ii_optimization(milp_solution=milp_solution)
                if pareto_front is None:  
                    logger.warning("NSGA-II optimization returned no results")
                    return {"best_solution": [], "iterations": None}

                # Process the Pareto front
                best_solution = None
                best_score = float('inf')

                # Adjusted weights
                weight_cost = 0.45
                weight_quality = 0.3  # Adjust as needed
                weight_availability = 0.15  # Adjust as needed
                weight_num_stores = 0.1  # Adjust as needed

                def normalize_cost(cost):
                    return (cost - 100) / (900)  # Assuming costs range from $100 to $1000

                def normalize_num_stores(num_stores):
                    return (num_stores - 1) / (19)  # Assuming store count ranges from 1 to 20

                for solution in pareto_front:
                    cost, quality, availability, num_stores = solution.fitness.values

                    normalized_cost = normalize_cost(cost)
                    normalized_num_stores = normalize_num_stores(num_stores)
                    # Composite score calculation
                    composite_score = (weight_cost * normalized_cost +
                                       weight_quality * quality +
                                       weight_availability * availability +
                                       weight_num_stores * normalized_num_stores)
                    
                    if composite_score < best_score:
                        logger.info("A new \"best solution\" was found: ")
                        logger.info(f"cost: {str(weight_cost * cost)} ({cost})")
                        logger.info(f"quality: {str(weight_quality * (1/quality))} ({quality})")
                        logger.info(f"availability: {str(weight_availability * (availability) )} ({availability})")
                        logger.info(f"num_stores: {str(weight_num_stores * num_stores)} ({num_stores})")
                        logger.info(f"composite_score vs old composite_score: {str(composite_score)} vs {str(best_score)}")

                        best_score = composite_score
                        best_solution = solution

                # Extract the purchasing plan from the best solution
                if best_solution:
                    # Convert indices to card data before processing
                    purchasing_details = []
                    for idx in best_solution:
                        if isinstance(idx, int) and idx in self.filtered_listings_df.index:
                            card_data = self.filtered_listings_df.loc[idx].to_dict()
                            purchasing_details.append(card_data)
                        elif isinstance(idx, (dict, pd.Series)):
                            purchasing_details.append(idx)

                    # Process each card's purchasing details
                    for card_data in purchasing_details:
                        # Find matching listing to get set_code
                        matching_listings = self.filtered_listings_df[
                            (self.filtered_listings_df['name'] == card_data['name']) &
                            (self.filtered_listings_df['site_name'] == card_data['site_name'])
                        ]
                        
                        if not matching_listings.empty:
                            card_data['set_code'] = matching_listings.iloc[0]['set_code']
                            card_data['set_name'] = matching_listings.iloc[0]['set_name']
                        else:
                            logger.warning(f"No matching listing found for {card_data['name']} at {card_data['site_name']}")
                            card_data['set_code'] = ''
                            card_data['set_name'] = ''

                    # Map the solution back to determine the purchasing plan
                    purchasing_plan = self.get_purchasing_plan(purchasing_details)

                    # Add set information only to plans missing them
                    for plan in purchasing_plan:
                        if 'set_code' not in plan or not plan['set_code']:
                            matching_listings = self.filtered_listings_df[
                                (self.filtered_listings_df['name'] == plan['name']) &
                                (self.filtered_listings_df['site_name'] == plan['site_name']) &
                                (self.filtered_listings_df['price'] == plan['price'])
                            ]
                            if not matching_listings.empty:
                                plan['set_code'] = matching_listings.iloc[0]['set_code']
                                plan['set_name'] = matching_listings.iloc[0]['set_name']
                            else:
                                logger.warning(f"No matching listing found for {plan['name']} at {plan['site_name']}")
                                plan['set_code'] = ''
                                plan['set_name'] = ''

                    # Create iterations from Pareto front with conditional set info addition
                    pareto_iterations = []
                    for idx, solution in enumerate(pareto_front):
                        iteration_plan = self.get_purchasing_plan(solution)
                        for plan in iteration_plan:
                            if 'set_code' not in plan or not plan['set_code']:
                                matching_listings = self.filtered_listings_df[
                                    (self.filtered_listings_df['name'] == plan['name']) &
                                    (self.filtered_listings_df['site_name'] == plan['site_name']) &
                                    (self.filtered_listings_df['price'] == plan['price'])
                                ]
                                if not matching_listings.empty:
                                    plan['set_code'] = matching_listings.iloc[0]['set_code']
                                    plan['set_name'] = matching_listings.iloc[0]['set_name']
                                else:
                                    plan['set_code'] = ''
                                    plan['set_name'] = ''

                        pareto_iterations.append({
                            'sorted_results_df': iteration_plan,
                            'total_price': sum(plan['total_price'] for plan in iteration_plan),
                            'number_store': len(set(plan['site_name'] for plan in iteration_plan)),
                            'nbr_card_in_solution': len(iteration_plan),
                            'list_stores': ', '.join(set(plan['site_name'] for plan in iteration_plan))
                        })

                    final_result = {
                        "best_solution": pd.DataFrame(purchasing_plan),
                        "iterations": pareto_iterations
                    }

            logger.info(f"Final optimization results:")
            logger.info(f"\tNumber of cards in best solution: {len(final_result.get('best_solution', []))}")
            logger.info(f"\tNumber of attempted solutions: {len(final_result.get('iterations', []))}")
            return final_result
        
        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}", exc_info=True)
            raise

    def _get_convergence_params(self):
        """Get convergence parameters based on problem size"""
        num_cards = len(self.user_wishlist_df)
        # Scale parameters with problem size
        return {
            'convergence_threshold': 0.01,
            'num_generations_threshold': max(10, min(20, num_cards // 4)),
            'min_generations': max(5, min(10, num_cards // 8)),
            'fitness_threshold': float('inf')  # Can be adjusted based on expected costs
        }

    def get_purchasing_plan(self, solution):
        return [{k: str(v) if isinstance(v, pd.Series) else v 
                 for k, v in plan.items()} 
                for plan in self._extract_purchasing_plan(
            solution, self.filtered_listings_df, self.user_wishlist_df
        )]
    
    def _find_alternative_listing(self, card_name, listings_df):
        """Find alternative listing when exact match isn't found"""
        matches = listings_df[listings_df['name'] == card_name]
        if not matches.empty:
            return matches.index[0]  # Return first matching index
        return None
    
    @staticmethod
    def _run_pulp(filtered_listings_df, user_wishlist_df, min_store, find_min_store):
        """Run MILP optimization"""
        try:
            # Validate and clean input data
            filtered_listings_df = filtered_listings_df.copy()
            
            # # Ensure site column is string and properly formatted
            # filtered_listings_df['site_name'] = filtered_listings_df['site_name'].fillna(
            #     filtered_listings_df['site_name']
            # ).astype(str)
            
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

            filtered_listings_df['site_name'] = filtered_listings_df['site_name'].combine_first(filtered_listings_df['site_name'])
            
            # Remove duplicates and validate columns
            filtered_listings_df = filtered_listings_df.loc[:, ~filtered_listings_df.columns.duplicated()]
            
            # logger.info(f"DataFrame columns after deduplication: {filtered_listings_df.columns.tolist()}")
            # logger.info(f"User wishlist columns: {user_wishlist_df.columns.tolist()}")
            # logger.info(f"Unique sites before optimization: {filtered_listings_df['site_name'].nunique()}")

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

            # Add weighted price calculation before costs dictionary creation
            filtered_listings_df['weighted_price'] = filtered_listings_df.apply(
                lambda row: row['price'] * QUALITY_WEIGHTS.get(row['quality'], QUALITY_WEIGHTS['DMG']), 
                axis=1
            )

            costs = {}
            for card in unique_cards:
                costs[card] = {}
                for store in unique_stores:
                    price = filtered_listings_df[
                        (filtered_listings_df["name"] == card) &
                        (filtered_listings_df["site_name"] == store)
                    ]["weighted_price"].min()
                    costs[card][store] = price if not pd.isna(price) else high_cost

            all_iterations_results = []

            # Validate minimum store requirement
            unique_stores = filtered_listings_df["site_name"].unique()
            if len(unique_stores) < min_store:
                logger.warning(f"Not enough stores available ({len(unique_stores)}) for minimum requirement ({min_store})")
                min_store = len(unique_stores)  # Adjust min_store to available stores
                
            logger.info(f"Running optimization with {len(unique_stores)} stores and minimum requirement of {min_store}")

            if not find_min_store:
                prob, buy_vars = PurchaseOptimizer._setup_prob(
                    costs, unique_cards, unique_stores, user_wishlist_df, min_store, total_qty
                )
                if pulp.LpStatus[prob.status] != "Optimal":
                    logger.warning("Solver did not find an optimal solution.")
                    return None, None  # Changed to match mtg_milp.py return value

                all_iterations_results = PurchaseOptimizer._process_result(
                    buy_vars, costs, total_qty, filtered_listings_df
                )
                return all_iterations_results["sorted_results_df"], None
            else:
                logger.info("Starting iterative algorithm")
                iteration = 1
                current_min = min_store
                all_iterations_results = []

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
                        total_qty
                    )
                    
                    logger.info(f"Solver solution: {pulp.LpStatus[prob.status]}")
                    if pulp.LpStatus[prob.status] != "Optimal":
                        logger.warning("Solver did not find an optimal solution.")
                        break
                    
                    iteration_results = PurchaseOptimizer._process_result(
                        buy_vars, costs, total_qty, filtered_listings_df
                    )
                    all_iterations_results.append(iteration_results)

                    # Add detailed iteration logging
                    completeness = iteration_results["nbr_card_in_solution"] == total_qty
                    status = "COMPLETE" if completeness else "INCOMPLETE"
                    percentage = 100.00 if completeness else (iteration_results["nbr_card_in_solution"] / total_qty) * 100
                    logger.info(
                        f"Iteration [{iteration}] Results:"
                        f"\n    Status: {status}"
                        f"\n    Cards Found: {iteration_results['nbr_card_in_solution']}/{total_qty} ({percentage:.2f}%)"
                        f"\n    Total Price: ${iteration_results['total_price']:.2f}"
                        f"\n    Stores Used: {iteration_results['number_store']}"
                        f"\n    Store Distribution: {iteration_results['list_stores']}"
                    )

                    iteration += 1
                    current_min -= 1

                if not all_iterations_results:
                    return None, None
                
                # Clean up temporary columns before returning
                filtered_listings_df = PurchaseOptimizer._cleanup_temporary_columns(df=filtered_listings_df)
                    
                # Modified to match main_v10.py logic - prioritize complete solutions
                complete_solutions = [
                    result for result in all_iterations_results 
                    if result["nbr_card_in_solution"] == total_qty
                ]

                if complete_solutions:
                    # Among complete solutions, find the cheapest
                    least_expensive_iteration = min(
                        complete_solutions,
                        key=lambda x: x["total_price"]
                    )
                else:
                    # If no complete solutions exist, take the most complete one
                    least_expensive_iteration = max(
                        all_iterations_results,
                        key=lambda x: (x["nbr_card_in_solution"], -x["total_price"])
                    )

                logger.info(
                    f"Best Iteration is with {least_expensive_iteration['number_store']} "
                    f"stores with a total price of: {least_expensive_iteration['total_price']:.2f}$ "
                    f"({least_expensive_iteration['nbr_card_in_solution']}/{total_qty} cards)"
                )

                return (
                    least_expensive_iteration["sorted_results_df"],
                    all_iterations_results
                )
        except Exception as e:
            logger.error("_run_pulp: %s", str(e))
            logger.error("DataFrame columns: %s", filtered_listings_df.columns.tolist())
            raise


    @staticmethod
    def _setup_prob(costs, unique_cards, unique_stores, user_wishlist, min_store, total_qty):
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

        prob += (
            pulp.lpSum(
                [buy_vars[card][store] * costs[card][store]
                 for card in unique_cards
                 for store in unique_stores]) +
            0.5 * pulp.lpSum([store_vars[store] for store in unique_stores])
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
    def _process_result(buy_vars, costs, total_qty, filtered_listings_df):
        Total_price = 0.0
        results = []
        total_card_nbr = 0
        
        found_cards = set()
        all_cards = set(card for card, _ in buy_vars.items())
        
        for card, store_dict in buy_vars.items():
            for store, var in store_dict.items():
                quantity = var.value()
                if quantity > 0:
                    price_per_unit = costs[card][store]
                    if price_per_unit != 10000:  # Only include cards in solution
                        card_store_total_price = quantity * price_per_unit
                        found_cards.add(card)
                        Total_price += card_store_total_price
                        total_card_nbr += quantity
                        
                        card_data = filtered_listings_df[
                            (filtered_listings_df["name"] == card) &
                            (filtered_listings_df["site_name"] == store)
                        ].iloc[0]
                        
                        results.append({
                            "name": card,
                            "site_name": store,
                            "price": float(price_per_unit),
                            "quality": card_data["quality"],
                            "quantity": int(quantity),
                            "set_name": card_data["set_name"],
                            "set_code": card_data["set_code"],
                            "version": card_data.get("version", "Standard"),
                            "foil": bool(card_data.get("foil", False)),
                            "language": card_data.get("language", "English"),
                            "site_id": card_data.get("site_id")
                        })

        results_df = pd.DataFrame(results)
        sorted_results_df = results_df.sort_values(by=["site_name", "name"])
        sorted_results_df.reset_index(drop=True, inplace=True)

        num_stores_used = len(sorted_results_df["site_name"].unique())
        store_counts = sorted_results_df["site_name"].value_counts()
        store_usage_str = ", ".join([f"{store}: {count}" for store, count in store_counts.items()])
        missing_cards = sorted(list(all_cards - found_cards))

        return {
            "nbr_card_in_solution": int(total_card_nbr),
            "total_price": float(Total_price),
            "number_store": int(num_stores_used),
            "list_stores": store_usage_str,
            "sorted_results_df": sorted_results_df,  # Keep as DataFrame
            "missing_cards": missing_cards,
            "missing_cards_count": len(missing_cards),
            "total_qty": total_qty
        }

    @staticmethod
    def _run_nsga_ii(filtered_listings_df, user_wishlist_df, milp_solution=None):
        """
        Run NSGA-II optimization with proper selection and elitism.
        
        Args:
            milp_solution: Optional solution from MILP to incorporate into initial population
            
        Returns:
            tools.ParetoFront: The final Pareto front of non-dominated solutions
        """

        if filtered_listings_df.empty or user_wishlist_df.empty:
            logger.error("Empty input dataframes")
            return None

        if not all(col in filtered_listings_df.columns for col in ['name', 'site_name', 'price', 'quality', 'quantity']):
            logger.error("Missing required columns in filtered_listings_df")
            return None

        toolbox = PurchaseOptimizer._initialize_toolbox(filtered_listings_df, user_wishlist_df)
        
        # Algorithm parameters
        NGEN = 50         # More generations
        MU = 100          # Smaller population
        CXPB = 0.7        # Higher crossover rate
        MUTPB = 0.3       # Higher mutation rate
        ELITISM_SIZE = 5  # Keep fewer elites
        
        # Initialize population with error handling
        if milp_solution:
            logger.info("Integrating MILP solution into initial population")
            milp_individual = PurchaseOptimizer._milp_solution_to_individual(milp_solution)
            pop = PurchaseOptimizer._initialize_population_with_milp(
                MU, filtered_listings_df, user_wishlist_df, milp_individual
            )
            if pop is None:  # Add this check
                logger.error("Failed to initialize population with MILP solution")
                pop = toolbox.population(n=MU)  # Fallback to random population
        else:
            logger.info("Initializing random population")
            pop = toolbox.population(n=MU)

        if not pop:  # Additional validation
            logger.error("Failed to initialize population")
            return None

        # Evaluate initial population
        logger.info("Evaluating initial population")
        fitnesses = map(toolbox.evaluate, pop)
        for ind, fit in zip(pop, fitnesses):
            ind.fitness.values = fit
        
        # Initialize Pareto front tracker
        pareto_front = tools.ParetoFront()
        pareto_front.update(pop)
        
        # Convergence parameters
        convergence_threshold = 0.01
        num_generations_threshold = 10
        best_fitness_so_far = float("inf")
        generations_without_improvement = 0
        
        # Evolution loop
        logger.info("Starting evolution")
        for gen in range(NGEN):
            logger.info(f"Generation {gen} started")
            
            # Selection for breeding
            offspring = toolbox.select(pop, len(pop) - ELITISM_SIZE)
            offspring = list(map(toolbox.clone, offspring))
            
            # Preserve elite individuals
            elite = tools.selBest(pop, ELITISM_SIZE)
            elite = list(map(toolbox.clone, elite))
            
            # Apply crossover and mutation on offspring
            for child1, child2 in zip(offspring[::2], offspring[1::2]):
                if random.random() < CXPB:
                    toolbox.mate(child1, child2)
                    del child1.fitness.values
                    del child2.fitness.values
                    
            for mutant in offspring:
                if random.random() < MUTPB:
                    toolbox.mutate(mutant)
                    del mutant.fitness.values
            
            # Evaluate invalid individuals
            invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
            fitnesses = map(toolbox.evaluate, invalid_ind)
            for ind, fit in zip(invalid_ind, fitnesses):
                ind.fitness.values = fit
            
            # Combine offspring and elite individuals
            pop = elite + offspring
            
            # Update Pareto front
            pareto_front.update(pop)

            def calculate_improvement(current, previous):
                if abs(previous) < 1e-10:
                    return abs(current - previous)
                elif not np.isfinite(previous) or not np.isfinite(current):
                    return float('inf')  # Force improvement check on first valid fitness
                else:
                    return abs(previous - current) / abs(previous)
                
            # Calculate statistics and check convergence
            current_best_fitness = tools.selBest(pop, 1)[0].fitness.values[0]
            relative_improvement = calculate_improvement(current_best_fitness, best_fitness_so_far)
            
            # Check for improvement
            if relative_improvement > convergence_threshold:
                best_fitness_so_far = current_best_fitness
                generations_without_improvement = 0
                logger.info(f"Improvement found in generation {gen}. Best fitness: {best_fitness_so_far:.2f}")
            else:
                generations_without_improvement += 1
                logger.info(f"No improvement in generation {gen}. Generations without improvement: {generations_without_improvement}")
            
            # Early stopping check
            if generations_without_improvement >= num_generations_threshold:
                logger.info(f"Convergence reached after {gen} generations")
                break
        
        logger.info("Evolution completed")
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
        # for i in range(max(len(ind1), len(ind2))):
        #     if i < len(ind1) and i < len(ind2) and random.random() < 0.5:
        #         ind1[i], ind2[i] = ind2[i], ind1[i]
        # return ind1, ind2 
        if len(ind1) > 2:  # Only crossover if we have enough points
            point = random.randint(1, len(ind1)-1)
            ind1[point:], ind2[point:] = ind2[point:], ind1[point:]
        return ind1, ind2

    @staticmethod
    def _initialize_individual(filtered_listings_df, user_wishlist_df):
        """Initialize an individual with the correct length based on wishlist quantities"""
        individual = []
        not_present = set()

        expected_length = sum(user_wishlist_df['quantity'])
        
        # Debug information
        #logger.info(f"Available cards in filtered_listings_df: {filtered_listings_df['name'].unique().tolist()}")
        #logger.info(f"Requested cards in wishlist: {user_wishlist_df['name'].tolist()}")
        
        for _, card in user_wishlist_df.iterrows():
            card_name = card["name"]
            required_quantity = int(card.get("quantity", 1))
            
            # Case-insensitive search for card name
            available_options = filtered_listings_df[
                filtered_listings_df["name"].str.lower() == card_name.lower()
            ]
            
            if not available_options.empty:
                # Add the same card multiple times based on required quantity
                for _ in range(required_quantity):
                    selected_option = available_options.sample(n=1)
                    individual.append(selected_option.index.item())
            else:
                # Debug information for missing cards
                logger.debug(f"Card '{card_name}' not found. Available cards containing this name:")
                similar_cards = filtered_listings_df[
                    filtered_listings_df["name"].str.lower().str.contains(
                        card_name.lower(), 
                        regex=False
                    )
                ]
                if not similar_cards.empty:
                    logger.debug(f"Similar cards found: {similar_cards['name'].unique().tolist()}")
                not_present.add(card_name)
                
        if not_present:
            logger.warning(f"Cards not found in filtered listings: {list(not_present)}")

        if len(individual) != expected_length:
            raise ValueError(f"Invalid individual length: {len(individual)} != {expected_length}")
                
        return creator.Individual(individual)

    @staticmethod
    def _milp_solution_to_individual(milp_solution):
        """Convert MILP solution to individual ensuring correct format"""
        try:
            if not milp_solution:
                return creator.Individual([])
                
            # Ensure the solution is converted to a list if it isn't already
            solution_list = (
                list(milp_solution) if isinstance(milp_solution, (list, tuple)) 
                else [milp_solution]
            )
            
            # Validate all elements are integers
            if not all(isinstance(x, (int, float)) for x in solution_list):
                logger.error("Invalid MILP solution - contains non-numeric values")
                return None

            return creator.Individual(solution_list)
        except Exception as e:
            logger.error(f"Error converting MILP solution: {str(e)}")
            return None

    @staticmethod
    def _custom_mutation(individual, filtered_listings_df, user_wishlist_df, indpb=0.05):
        for i in range(len(individual)):
            if random.random() < indpb:
                card_name = user_wishlist_df.iloc[i % len(user_wishlist_df)]["name"]
                # Get all available options for this card
                available_options = filtered_listings_df[
                    filtered_listings_df["name"] == card_name
                ]
                if not available_options.empty:
                    # Choose a random option weighted by quality and inverse price
                    weights = [
                        QUALITY_WEIGHTS.get(r["quality"], 0) / (float(r["price"]) + 0.1)
                        for _, r in available_options.iterrows()
                    ]
                    individual[i] = random.choices(
                        available_options.index,
                        weights=weights,
                        k=1
                    )[0]
        return (individual,)

    @staticmethod
    def _evaluate_solution_wrapper(filtered_listings_df, user_wishlist_df):
        def evaluate_solution(individual):
            # Initialize trackers
            total_cost = 0
            total_quality_score = 0
            stores = set()
            card_counts = defaultdict(int)  # Track how many of each card we have
            
            # Required quantities
            required_quantities = {
                row["name"]: row["quantity"] 
                for _, row in user_wishlist_df.iterrows()
            }
            
            # Process each card in the individual
            for idx in individual:
                if idx not in filtered_listings_df.index:
                    continue
                    
                card_row = filtered_listings_df.loc[idx]
                card_name = card_row["name"]
                card_counts[card_name] += 1
                
                # Only count costs/quality if we actually need this card
                if card_counts[card_name] <= required_quantities.get(card_name, 0):
                    # Base price
                    price = float(card_row["price"])
                    
                    # Quality adjustment
                    quality_multiplier = QUALITY_WEIGHTS.get(card_row["quality"], QUALITY_WEIGHTS["DMG"])
                    total_cost += price * quality_multiplier
                    
                    # Add quality score
                    total_quality_score += QUALITY_WEIGHTS.get(card_row["quality"], 0)
                    
                    # Track store
                    stores.add(card_row["site_name"])
            
            # Calculate scores
            # 1. Check if we have enough of each card
            missing_cards = sum(
                max(0, required_quantities[name] - count)
                for name, count in card_counts.items()
            )
            
            # 2. Calculate availability score
            availability_score = sum(
                1 for name, count in card_counts.items()
                if count >= required_quantities.get(name, 0)
            ) / len(required_quantities)
            
            # 3. Normalize quality score
            quality_score = total_quality_score / len(individual) if individual else 0
            
            # Apply penalties
            cost_with_penalties = (
                total_cost +
                missing_cards * 10000 +  # Heavy penalty for missing cards
                (len(stores) - 1) * 100   # Small penalty for each additional store
            )
            
            return (
                cost_with_penalties,
                quality_score,
                availability_score,
                len(stores)
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
                    # Get qualities and validate them
                    quality_weights = QUALITY_WEIGHTS
                    required_quality = user_wishlist_row.get("quality", "NM")
                    required_quality = PurchaseOptimizer._validate_quality(required_quality, quality_weights, "NM")
                    card_quality = card_row.get("quality", "NM")
                    card_quality = PurchaseOptimizer._validate_quality(card_quality, quality_weights, "DMG")
                    
                    # Check if card quality meets or exceeds required quality
                    quality_check = (required_quality == card_quality or 
                                    quality_weights[card_quality] <= quality_weights[required_quality])
                    
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
                                "site_name": card_row.get("site_name"),
                                "quality": card_quality,
                                "price": price,
                                "total_price": price * available_quantity,
                                "quality_match": required_quality == card_quality
                            }
                            purchasing_plan.append(purchase_details)

                            # Update user wishlist using a copy to avoid side effects
                            user_wishlist_df_copy = user_wishlist_df.copy()
                            mask = user_wishlist_df_copy["name"] == card_name
                            user_wishlist_df_copy.loc[mask, "quantity"] -= available_quantity
                            user_wishlist_df = user_wishlist_df_copy

            except Exception as e:
                logger.warning(f"Error processing card {card_row if 'card_row' in locals() else 'unknown'}: {str(e)}")
                continue

        # Remove entries with zero quantity left
        user_wishlist_df = user_wishlist_df[user_wishlist_df["quantity"] > 0]

        return purchasing_plan

    @staticmethod
    def _initialize_population_with_milp(n, filtered_listings_df, user_wishlist_df, milp_solution):
        try:
            expected_length = sum(user_wishlist_df['quantity'])
            if milp_solution and len(milp_solution) != expected_length:
                logger.warning(f"MILP solution length {len(milp_solution)} does not match expected length {expected_length}")
                return None

            # Initialize population with error handling
            population = []
            for _ in range(n - 1):
                try:
                    individual = PurchaseOptimizer._initialize_individual(filtered_listings_df, user_wishlist_df)
                    if individual is not None:
                        population.append(individual)
                except Exception as e:
                    logger.warning(f"Failed to initialize individual: {str(e)}")
                    continue

            if not population:
                logger.error("Failed to initialize any individuals")
                return None

            milp_individual = PurchaseOptimizer._milp_solution_to_individual(milp_solution)
            if milp_individual is not None:
                population.insert(0, milp_individual)

            return population

        except Exception as e:
            logger.error(f"Error in _initialize_population_with_milp: {str(e)}")
            return None
    
    @staticmethod
    def _cleanup_temporary_columns(df):  # Removed 'self' parameter
        temp_columns = ['Identifier', 'weighted_price', 'site_info']  # Added 'site_info' to columns to clean
        for col in temp_columns:
            if col in df.columns:
                df = df.drop(columns=[col])
        return df
    
    @staticmethod
    def _validate_quality(quality, quality_weights, default="NM"):
        return quality if quality in quality_weights else default