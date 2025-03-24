import logging
import random
from collections import defaultdict
from functools import partial
from typing import Dict

import numpy as np
import pandas as pd
import pulp
from app.constants import LANGUAGE_WEIGHTS, QUALITY_WEIGHTS, CardQuality
from app.utils.data_fetcher import ErrorCollector
from deap import algorithms, base, creator, tools

logger = logging.getLogger(__name__)

# DEAP Setup
creator.create(
    "FitnessMulti",
    base.Fitness,
    weights=(
        -1.0,  # Minimize cost
        1.0,  # Maximize quality
        100.0,  # Heavily prioritize availability
        -0.1,  # Slightly penalize store count
    ),
)
creator.create("Individual", list, fitness=creator.FitnessMulti)


class PurchaseOptimizer:
    def __init__(self, filtered_listings_df, user_wishlist_df, config):
        # Update column mapping to match actual DataFrame columns
        self.column_mapping = {
            "name": "name",
            "site_name": "site_name",  # Changed from site_name to site
            "price": "price",
            "quality": "quality",
            "quantity": "quantity",
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
        self.language_weights = LANGUAGE_WEIGHTS

        self._validate_input_data()

        # Add validation for sites
        unique_sites = filtered_listings_df["site_name"].nunique()
        if unique_sites < config.get("min_store", 1):
            logger.warning(f"Found only {unique_sites} sites, but minimum {config.get('min_store')} required")
            # Adjust min_store if needed
            config["min_store"] = min(unique_sites, config.get("min_store", 1))

        logger.info(f"Initializing optimizer with {unique_sites} unique sites")

    def _standardize_dataframe(self, df):
        """Standardize DataFrame column names and validate quality values"""
        df = df.copy()

        # Rename columns based on mapping
        df = df.rename(columns=self.column_mapping)

        # Ensure all required columns exist
        for required_col in self.column_mapping.values():
            if required_col not in df.columns:
                logger.warning(f"Missing column {required_col}, creating with default values")
                if required_col in ["price", "quantity"]:
                    df[required_col] = 0
                elif required_col == "quality":
                    df[required_col] = "HP"
                elif required_col == "site_name":
                    df[required_col] = df["site_id"].astype(str)
                else:
                    df[required_col] = ""
        # Standardize price values
        if "price" in df.columns:
            try:
                # Convert to float first to handle any string prices
                df["price"] = pd.to_numeric(df["price"], errors="coerce")
                # Round to 2 decimal places
                df["price"] = df["price"].round(2)
                # Fill any NaN values with 0
                df["price"] = df["price"].fillna(0)
            except Exception as e:
                logger.error(f"Error standardizing prices: {e}")

        # Validate and normalize quality values
        if "quality" in df.columns:
            try:
                df = CardQuality.validate_and_update_qualities(df, quality_column="quality")
            except Exception as e:
                logger.warning(f"Error normalizing qualities: {e}")

        # min_quality_weight = QUALITY_WEIGHTS.get("DMG", 0)  # Use DMG instead of HP
        # df = df[df["quality"].apply(lambda q: QUALITY_WEIGHTS[q] >= min_quality_weight)]

        return df

    def _validate_input_data(self):
        """Validate input data structure and content"""
        required_columns = {
            "filtered_listings": ["name", "site_name", "price", "quality", "quantity"],
            "user_wishlist": ["name", "quantity", "min_quality"],  # Ensure min_quality is included
        }

        for df_name, columns in required_columns.items():
            df = getattr(self, f"{df_name}_df")
            missing_cols = [col for col in columns if col not in df.columns]
            if missing_cols:
                logger.error(f"DataFrame {df_name} columns: {df.columns.tolist()}")
                logger.error(f"Missing columns in {df_name}: {missing_cols}")
                raise ValueError(f"Missing required columns in {df_name}: {missing_cols}")

            # Validate data types
            if df_name == "card_details":
                if not pd.to_numeric(df["price"], errors="coerce").notnull().all():
                    raise ValueError("Price column contains non-numeric values")
                if not pd.to_numeric(df["quantity"], errors="coerce").notnull().all():
                    raise ValueError("Quantity column contains non-numeric values")

    def run_optimization(self, card_names, config):
        try:
            error_collector = ErrorCollector.get_instance()  # Initialize error_collector
            milp_result = None
            # Debug incoming data
            logger.debug(f"Input DataFrame columns: {self.filtered_listings_df.columns.tolist()}")

            self.filtered_listings_df["site_name"] = self.filtered_listings_df["site_name"].astype(str)
            self.filtered_listings_df = self.filtered_listings_df[self.filtered_listings_df["name"].isin(card_names)]

            if self.filtered_listings_df.empty:
                logger.error("No matching cards found in listings")
                return {"best_solution": [], "iterations": None}

            # Add logging for unique available cards
            # available_cards = sorted(self.filtered_listings_df['name'].unique())
            # logger.info(f"Available cards ({len(available_cards)}): {available_cards}")

            logger.info(f"Starting optimization with {len(card_names)} cards")
            logger.info(f"Found {self.filtered_listings_df['site_name'].nunique()}/{config["max_store"]} unique sites")
            # logger.info(f"Unique sites: {self.filtered_listings_df['site_name'].unique().tolist()}")

            final_result = None
            best_solution_records = None
            if config["milp_strat"] or config["hybrid_strat"]:
                logger.info("Running MILP optimization...")
                best_solution, all_milp_solutions = self.run_milp_optimization()
                self.filtered_listings_df = self._cleanup_temporary_columns(df=self.filtered_listings_df)

                if best_solution is not None:
                    # Create standardized solution format
                    best_milp_solution_found = self._create_standardized_solution(
                        best_solution if isinstance(best_solution, list) else best_solution.to_dict("records")
                    )
                    best_solution_records = (
                        best_solution.to_dict("records") if isinstance(best_solution, pd.DataFrame) else best_solution
                    )

                    # Format iterations using standardized format
                    milp_iterations = []
                    if all_milp_solutions:
                        for solution in all_milp_solutions:
                            # iteration_copy = self._create_standardized_solution(
                            #     solution['sorted_results_df'] if isinstance(solution['sorted_results_df'], pd.DataFrame)
                            #     else solution['sorted_results_df']
                            # )
                            # formatted_iterations.append(iteration_copy)
                            milp_iterations.append(solution)

                    milp_result = {
                        "status": "success",
                        "best_solution": best_milp_solution_found,
                        "iterations": milp_iterations,
                        "type": "milp",
                    }
                    final_result = milp_result
                    if not config["hybrid_strat"]:
                        formatted_summary = self.format_optimization_summary(milp_result)
                        logger.info(f"Summary of Milp optimization:")
                        logger.info(f"{formatted_summary}")
                else:
                    logger.warning("MILP optimization returned no results")

            if config["nsga_strat"] or config["hybrid_strat"]:
                logger.info("Running NSGA-II optimization...")
                milp_solution = None

                if config["hybrid_strat"] and milp_result and milp_result.get("best_solution"):
                    milp_solution = best_solution_records
                    # milp_solution = final_result["best_solution"]

                best_nsga_solution_found, nsga_iterations = self.run_nsga_ii_optimization(milp_solution=milp_solution)

                if best_nsga_solution_found and nsga_iterations:
                    logger.info("Best NSGA-II Solution Found:")
                    logger.info(f"Cards Found:    {best_nsga_solution_found['nbr_card_in_solution']}")
                    logger.info(f"Missing Cards:  {best_nsga_solution_found['missing_cards_count']}")
                    logger.info(f"Total Cost:    ${best_nsga_solution_found['total_price']:.2f}")
                    logger.info(f"Stores Used:   {best_nsga_solution_found['number_store']}")

                    nsga_result = {
                        "status": "success",
                        "best_solution": best_nsga_solution_found,
                        "iterations": nsga_iterations,
                        "type": "nsga",
                    }

                    # For hybrid strategy, compare and select the better solution
                    if config["hybrid_strat"] and milp_result:
                        logger.info("Comparing Solutions:")
                        logger.info("=" * 80)
                        logger.info("MILP Solution:")
                        logger.info(f"Cards Found:    {milp_result['best_solution']['nbr_card_in_solution']}")
                        logger.info(f"Missing Cards:  {milp_result['best_solution']['missing_cards_count']}")
                        logger.info(f"Total Cost:    ${milp_result['best_solution']['total_price']:.2f}")
                        logger.info(f"total number of iterations: {len(milp_result['iterations'])}")
                        logger.info("-" * 80)

                        logger.info("NSGA-II Solution:")
                        logger.info(f"Cards Found:    {nsga_result['best_solution']['nbr_card_in_solution']}")
                        logger.info(f"Missing Cards:  {nsga_result['best_solution']['missing_cards_count']}")
                        logger.info(f"Total Cost:    ${nsga_result['best_solution']['total_price']:.2f}")
                        logger.info(f"total number of iterations: {len(nsga_result['iterations'])}")
                        logger.info("=" * 80)

                        # Select the better solution
                        final_result = self._select_final_solution(milp_result, nsga_result)
                    else:
                        final_result = nsga_result
                else:
                    logger.warning("NSGA-II optimization returned no results")

            if final_result and final_result.get("status") == "success":
                final_result["errors"] = {
                    "unreachable_stores": list(error_collector.unreachable_stores),
                    "unknown_languages": list(error_collector.unknown_languages),
                    "unknown_qualities": list(error_collector.unknown_qualities),
                }
                formatted_summary = self.format_optimization_summary(final_result)
                logger.info(f"Summary of optimization:")
                for item in formatted_summary:
                    logger.info(item)
                return final_result
            else:
                logger.error("Optimization failed to produce valid results")
                return {
                    "status": "failed",
                    "best_solution": [],
                    "iterations": None,
                    "errors": {
                        "unreachable_stores": list(error_collector.unreachable_stores),
                        "unknown_languages": list(error_collector.unknown_languages),
                        "unknown_qualities": list(error_collector.unknown_qualities),
                    },
                }

        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}", exc_info=True)
            return {
                "status": "failed",
                "best_solution": [],
                "iterations": None,
                "errors": {"unreachable_stores": [], "unknown_languages": [], "unknown_qualities": []},
            }

    def format_optimization_summary(self, final_result):
        """Format optimization results in a human-readable way"""
        try:
            # Extract solution data
            best_solution = final_result.get("best_solution", {})
            iterations = final_result.get("iterations", [])
            opt_type = final_result.get("type", "unknown")

            # Get the actual card data from the standardized format
            if isinstance(best_solution, dict):
                # If it's the standardized format, get the stores data
                stores = best_solution.get("stores", [])
                cards_data = []
                for store in stores:
                    cards_data.extend(store.get("cards", []))

                # Get pre-calculated statistics
                total_price = best_solution.get("total_price", 0)
                cards_found = best_solution.get("nbr_card_in_solution", 0)
                store_count = best_solution.get("number_store", 0)
                missing_count = best_solution.get("missing_cards_count", 0)

            elif isinstance(best_solution, pd.DataFrame):
                # Handle DataFrame format
                cards_data = best_solution.to_dict("records")
                total_price = sum(float(card["price"]) * int(card["quantity"]) for card in cards_data)
                cards_found = len(cards_data)
                store_count = len(set(card["site_name"] for card in cards_data))
                missing_count = 0  # Would need additional context to calculate

            else:
                # Handle direct list format
                cards_data = best_solution if isinstance(best_solution, list) else []
                total_price = sum(float(card["price"]) * int(card["quantity"]) for card in cards_data)
                cards_found = len(cards_data)
                store_count = len(set(card["site_name"] for card in cards_data))
                missing_count = 0

            # Calculate quality distribution
            quality_counts = defaultdict(int)
            total_cards = 0
            for card in cards_data:
                quantity = int(card.get("quantity", 1))
                quality = card.get("quality", "Unknown")
                quality_counts[quality] += quantity
                total_cards += quantity

            # Format the summary
            summary = [
                "Final Optimization Results:",
                f"{'='*50}",
                f"Optimization Type:  {opt_type}",
                f"Cards Found:        {cards_found} cards",
                f"Missing Cards:      {missing_count} cards",
                f"Total Cost:         ${total_price:.2f}",
                f"Stores Used:        {store_count} stores",
                f"Solutions Tried:    {len(iterations)}",
                "",
                "Quality Distribution:",
                "-" * 50,
            ]

            if total_cards > 0:
                for quality, count in sorted(quality_counts.items()):
                    percentage = (count / total_cards) * 100
                    summary.append(f"{quality:<15} {count:>3} cards ({percentage:>5.1f}%)")
            else:
                summary.append("No cards in solution")

            # Add store distribution if available
            summary.append("")
            summary.append("Store Distribution")
            summary.append("-" * 50)
            if isinstance(best_solution, dict) and "list_stores" in best_solution:
                for store in best_solution["list_stores"].split(", "):
                    summary.append(store)

            return summary

        except Exception as e:
            logger.error(f"Error formatting optimization summary: {str(e)}", exc_info=True)
            return (
                f"Optimization completed ({opt_type})\n"
                f"Cards found: {cards_found}\n"
                f"Total cost: ${total_price:.2f}"
            )

    def _find_best_solution(self, solutions):
        """Find the best solution from a list of standardized solutions"""
        if not solutions:
            return None

        # First prioritize completeness
        complete_solutions = [sol for sol in solutions if sol["nbr_card_in_solution"] == len(self.user_wishlist_df)]

        if complete_solutions:
            # Among complete solutions, choose the one with lowest cost
            return min(
                complete_solutions,
                key=lambda x: (
                    x["total_price"],  # First priority: minimize cost
                    x["number_store"],  # Second priority: minimize stores
                ),
            )

        # If no complete solutions, choose the one with most cards
        return max(
            solutions,
            key=lambda x: (
                x["nbr_card_in_solution"],  # First priority: maximize cards found
                -x["total_price"],  # Second priority: minimize cost
            ),
        )

    def _select_final_solution(self, milp_result, nsga_result):
        """Select the better solution between MILP and NSGA-II results"""
        milp_solution = milp_result["best_solution"]
        nsga_solution = nsga_result["best_solution"]
        total_iterations = len(milp_result["iterations"]) + len(nsga_result["iterations"])
        logger.info(f"Total iterations: {total_iterations}")
        complete_set_of_iterations = milp_result["iterations"] + nsga_result["iterations"]

        # Compare completeness first
        milp_complete = milp_solution["nbr_card_in_solution"] == len(self.user_wishlist_df)
        nsga_complete = nsga_solution["nbr_card_in_solution"] == len(self.user_wishlist_df)

        if milp_complete and not nsga_complete:
            logger.info("Selected MILP solution (complete vs incomplete)")
            milp_result["iterations"] = complete_set_of_iterations
            return milp_result
        elif nsga_complete and not milp_complete:
            logger.info("Selected NSGA-II solution (complete vs incomplete)")
            nsga_result["iterations"] = complete_set_of_iterations
            return nsga_result

        # If both complete or both incomplete, compare cards found
        if milp_solution["nbr_card_in_solution"] > nsga_solution["nbr_card_in_solution"]:
            logger.info("Selected MILP solution (more cards found)")
            milp_result["iterations"] = complete_set_of_iterations
            return milp_result
        elif nsga_solution["nbr_card_in_solution"] > milp_solution["nbr_card_in_solution"]:
            logger.info("Selected NSGA-II solution (more cards found)")
            nsga_result["iterations"] = complete_set_of_iterations
            return nsga_result

        # If equal cards found, compare cost
        if milp_solution["total_price"] <= nsga_solution["total_price"]:
            logger.info("Selected MILP solution (lower/equal cost)")
            milp_result["iterations"] = complete_set_of_iterations
            return milp_result
        else:
            logger.info("Selected NSGA-II solution (lower cost)")
            nsga_result["iterations"] = complete_set_of_iterations
            return nsga_result

    def _create_failed_result(self, error_collector):
        """Create a standardized failed result"""
        return {
            "status": "failed",
            "best_solution": [],
            "iterations": None,
            "errors": {
                "unreachable_stores": list(error_collector.unreachable_stores),
                "unknown_languages": list(error_collector.unknown_languages),
                "unknown_qualities": list(error_collector.unknown_qualities),
            },
        }

    def _standardize_nsga_solution(self, solution_indices, filtered_listings_df, user_wishlist_df):
        """
        Standardize NSGA-II solution format to match MILP output structure.

        Args:
            solution_indices: List of indices from NSGA-II solution
            filtered_listings_df: DataFrame containing all available card listings
            user_wishlist_df: DataFrame containing user's wishlist

        Returns:
            dict: Standardized solution matching MILP output format
        """
        try:
            # Convert indices to card data
            purchasing_plan = []
            processed_cards = defaultdict(int)

            for idx in solution_indices:
                if idx not in filtered_listings_df.index:
                    continue

                card_data = filtered_listings_df.loc[idx].to_dict()
                card_name = card_data["name"]

                # Match against user wishlist
                wishlist_row = user_wishlist_df[user_wishlist_df["name"] == card_name]
                if wishlist_row.empty:
                    continue

                required_quantity = int(wishlist_row.iloc[0]["quantity"])
                remaining_needed = required_quantity - processed_cards[card_name]

                if remaining_needed > 0:
                    card_data["quantity"] = 1  # NSGA-II indices represent individual cards
                    purchasing_plan.append(card_data)
                    processed_cards[card_name] += 1

            # Calculate solution metrics
            total_price = sum(float(card["price"]) * int(card["quantity"]) for card in purchasing_plan)

            total_qty = sum(int(card["quantity"]) for card in purchasing_plan)

            # Group cards by store
            stores_data = defaultdict(list)
            for card in purchasing_plan:
                stores_data[card["site_name"]].append(card)

            # Create store distribution string
            store_usage_str = ", ".join(f"{store}: {len(cards)}" for store, cards in stores_data.items())

            # Create final store structure ICI
            stores = [
                {"site_name": store, "site_id": cards[0]["site_id"], "cards": cards}
                for store, cards in stores_data.items()
            ]

            # Create sorted DataFrame
            sorted_results_df = pd.DataFrame(purchasing_plan).sort_values(by=["site_name", "name"])
            sorted_results_df.reset_index(drop=True, inplace=True)

            # Identify missing cards
            found_cards = set(card["name"] for card in purchasing_plan)
            all_cards = set(user_wishlist_df["name"])
            missing_cards = list(all_cards - found_cards)

            return {
                "nbr_card_in_solution": len(purchasing_plan),
                "total_price": float(total_price),
                "number_store": len(stores),
                "list_stores": store_usage_str,
                "stores": stores,
                "total_qty": total_qty,
                "sorted_results_df": sorted_results_df,
                "missing_cards": missing_cards,
                "missing_cards_count": len(missing_cards),
            }

        except Exception as e:
            logger.error(f"Error in _standardize_nsga_solution: {str(e)}", exc_info=True)
            return None

    def _create_standardized_solution(self, solution_data):
        """Create standardized solution format from raw purchasing plan."""
        if not isinstance(solution_data, list) or not all(isinstance(item, dict) for item in solution_data):
            logger.error("Invalid solution data format. Expected a list of dictionaries.")
            raise ValueError("Invalid solution data format.")

        # Validate required fields
        required_fields = ["name", "site_name", "price", "quantity"]
        if not all(key in solution_data[0] for key in required_fields):
            logger.error("Solution data missing required fields.")
            raise ValueError("Invalid solution data format.")

        # Standardize solution
        purchasing_plan = solution_data
        total_price = sum(card["price"] * card["quantity"] for card in purchasing_plan)
        stores_data = defaultdict(list)
        total_qty = len(purchasing_plan)

        for card in purchasing_plan:
            stores_data[card["site_name"]].append(card)

        stores = [
            {"site_name": store, "site_id": cards[0]["site_id"], "cards": cards} for store, cards in stores_data.items()
        ]
        sorted_results_df = pd.DataFrame(purchasing_plan).sort_values(by=["site_name", "name"])

        # Identify missing cards
        found_cards = set(card["name"] for card in purchasing_plan)
        all_cards = set(self.user_wishlist_df["name"])
        missing_cards = list(all_cards - found_cards)

        return {
            "nbr_card_in_solution": len(purchasing_plan),
            "total_price": total_price,
            "number_store": len(stores),
            "list_stores": ", ".join(f"{store}: {len(cards)}" for store, cards in stores_data.items()),
            "stores": stores,
            "total_qty": total_qty,
            "sorted_results_df": sorted_results_df,
            "missing_cards": missing_cards,
            "missing_cards_count": len(missing_cards),
        }

    @staticmethod
    def _convert_solution_to_indices(solution, filtered_listings_df):
        """
        Convert MILP solution to indices for genetic algorithm.

        Args:
            solution (list): List of dictionaries containing card solutions from MILP
            filtered_listings_df (pd.DataFrame): DataFrame containing all possible card listings

        Returns:
            list: List of indices that can be used by the genetic algorithm
        """
        indices = []
        missing_records = []

        # Ensure price columns are rounded to same precision
        filtered_listings_df["price"] = filtered_listings_df["price"].round(2)

        for record in solution:
            # Round the price in the record to match DataFrame precision
            record_price = round(float(record["price"]), 2)

            # Create mask for matching records
            mask = (
                (filtered_listings_df["name"] == record["name"])
                & (filtered_listings_df["site_name"] == record["site_name"])
                & (filtered_listings_df["price"].round(2) == record_price)
            )

            matching_rows = filtered_listings_df[mask]

            if matching_rows.empty:
                # Try a more lenient search if exact match fails
                alternate_mask = (filtered_listings_df["name"] == record["name"]) & (
                    filtered_listings_df["site_name"] == record["site_name"]
                )
                alternate_rows = filtered_listings_df[alternate_mask]

                if not alternate_rows.empty:
                    # Take the closest price match
                    closest_match = alternate_rows.iloc[(alternate_rows["price"] - record_price).abs().argmin()]
                    indices.append(closest_match.name)  # .name gets the index
                    # logger.info(f"Used closest price match for {record['name']}")
                else:
                    missing_records.append(record)
            else:
                # if len(matching_rows) > 1:
                #     logger.info(f"Multiple matches found for {record['name']}, using first match")
                indices.append(matching_rows.index[0])

        if missing_records:
            logger.warning(
                f"Could not match {len(missing_records)} records from MILP solution. "
                f"Original solution size: {len(solution)}, Converted indices: {len(indices)}"
            )

        # Validate indices
        if not all(isinstance(idx, (int, np.integer)) for idx in indices):
            logger.error("Invalid indices found after conversion")
            return None

        # Create valid individual for genetic algorithm
        try:
            return creator.Individual(indices)
        except Exception as e:
            logger.error(f"Failed to create individual: {str(e)}")
            return None

    @staticmethod
    def _setup_pulp_optimization(filtered_listings_df, user_wishlist_df):
        """Set up the MILP optimization problem with data validation and preprocessing."""
        try:
            # Validate input data
            if user_wishlist_df is None or user_wishlist_df.empty:
                logger.error("user_wishlist_df is None or empty")
                return None, None, None, None, None

            if filtered_listings_df is None or filtered_listings_df.empty:
                logger.error("filtered_listings_df is None or empty")
                return None, None, None, None, None

            # Clean and prepare data
            filtered_listings_df = filtered_listings_df.copy()
            filtered_listings_df["site_name"] = filtered_listings_df["site_name"].combine_first(
                filtered_listings_df["site_name"]
            )
            filtered_listings_df = filtered_listings_df.loc[:, ~filtered_listings_df.columns.duplicated()]

            # Get unique values
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

            # total_qty = len(user_wishlist_df)
            total_qty = user_wishlist_df["quantity"].sum()

            high_cost = 10000  # High cost for unavailable combinations

            # Calculate weighted prices
            filtered_listings_df["weighted_price"] = filtered_listings_df.apply(
                lambda row: row["price"]
                * (
                    QUALITY_WEIGHTS.get(row["quality"], QUALITY_WEIGHTS["DMG"])
                    * LANGUAGE_WEIGHTS.get(row.get("language", "Unknown"), LANGUAGE_WEIGHTS["default"])
                ),
                axis=1,
            )

            # Create costs dictionary
            costs = {}
            for card in unique_cards:
                costs[card] = {}
                for store in unique_stores:
                    price = filtered_listings_df[
                        (filtered_listings_df["name"] == card) & (filtered_listings_df["site_name"] == store)
                    ]["weighted_price"].min()
                    costs[card][store] = price if not pd.isna(price) else high_cost

            return filtered_listings_df, unique_cards, unique_stores, costs, total_qty

        except Exception as e:
            logger.error(f"Error in setup_pulp_optimization: {str(e)}", exc_info=True)
            return None, None, None, None, None

    @staticmethod
    def _compute_pulp_optimization(
        filtered_listings_df, user_wishlist_df, unique_cards, unique_stores, costs, total_qty, min_store, find_min_store
    ):
        """Run the MILP optimization with the setup data."""
        try:
            all_iterations_results = []
            best_complete_solution = None

            if find_min_store:
                logger.info("Starting minimum store search optimization:")
                logger.info("=" * 50)
                logger.info(f"Total cards to find: {total_qty}")
                logger.info(f"Available stores: {len(unique_stores)}")

                # Track best solutions by completeness first, then cost
                complete_solutions = []

                for store_count in range(1, len(unique_stores) + 1):

                    logger.info("=" * 30)
                    logger.info(f"Trying solution with {store_count} stores:")
                    logger.info("-" * 30)

                    prob, buy_vars = PurchaseOptimizer._setup_prob(
                        costs, unique_cards, unique_stores, user_wishlist_df, store_count
                    )

                    if pulp.LpStatus[prob.status] == "Optimal":
                        iteration_results = PurchaseOptimizer._process_result(buy_vars, costs, filtered_listings_df)
                        all_iterations_results.append(iteration_results)

                        cards_found = iteration_results["nbr_card_in_solution"]
                        weighted_cost = sum(
                            costs[card][store] * var.value()
                            for card, store_dict in buy_vars.items()
                            for store, var in store_dict.items()
                            if var.value() > 0
                        )
                        actual_cost = iteration_results["total_price"]

                        logger.info(f"Cards Found:     {cards_found}/{total_qty}")
                        logger.info(f"Weighted Cost:   ${weighted_cost:.2f}")
                        logger.info(f"Actual Cost:     ${actual_cost:.2f}")
                        logger.info(f"Stores Used:     {iteration_results['number_store']}")

                        if cards_found == total_qty:  # Complete solution
                            complete_solutions.append(iteration_results)

                            # Update best complete solution if this is better
                            if best_complete_solution is None or actual_cost < best_complete_solution["total_price"]:
                                best_complete_solution = iteration_results
                                logger.info(">>> New best complete solution found!")
                                logger.info(f"Store Distribution:")
                                for store_info in iteration_results["list_stores"].split(", "):
                                    logger.info(f"  {store_info}")

                            # Check if we're getting diminishing returns
                            if len(complete_solutions) > 1:
                                cost_improvement = (
                                    complete_solutions[-2]["total_price"] - complete_solutions[-1]["total_price"]
                                )
                                if cost_improvement < complete_solutions[-1]["total_price"] * 0.01:  # 1% threshold
                                    logger.info("Stopping search - minimal cost improvement")
                                    break
                    else:
                        logger.info(f"No feasible solution found with {store_count} stores")

                if complete_solutions:
                    # Find best solution with minimum stores within 5% of best price
                    best_price = min(sol["total_price"] for sol in complete_solutions)
                    min_store_solutions = [sol for sol in complete_solutions if sol["total_price"] <= best_price * 1.05]
                    best_solution = min(min_store_solutions, key=lambda x: x["number_store"])

                    logger.info("Final Solution Selected:")
                    logger.info("=" * 30)
                    logger.info(f"Total Cost:    ${best_solution['total_price']:.2f}")
                    logger.info(f"Cards Found:   {best_solution['nbr_card_in_solution']}/{total_qty}")
                    logger.info(f"Stores Used:   {best_solution['number_store']}")
                    logger.info("Distribution:")
                    for store_info in best_solution["list_stores"].split(", "):
                        logger.info(f"  {store_info}")

                    return best_solution["sorted_results_df"], all_iterations_results

                logger.warning("No complete solutions found")
                return None, all_iterations_results

            else:
                logger.info("Starting optimization with minimum store constraint:")
                logger.info("=" * 50)
                logger.info(f"Total cards to find: {total_qty}")
                logger.info(f"Minimum stores required: {min_store}")
                logger.info(f"Available stores: {len(unique_stores)}")

                prob, buy_vars = PurchaseOptimizer._setup_prob(
                    costs, unique_cards, unique_stores, user_wishlist_df, min_store
                )

                if pulp.LpStatus[prob.status] == "Optimal":
                    iteration_results = PurchaseOptimizer._process_result(buy_vars, costs, filtered_listings_df)
                    all_iterations_results.append(iteration_results)

                    cards_found = iteration_results["nbr_card_in_solution"]
                    actual_cost = iteration_results["total_price"]

                    logger.info(f"Cards Found:     {cards_found}/{total_qty}")
                    logger.info(f"Total Cost:      ${actual_cost:.2f}")
                    logger.info(f"Stores Used:     {iteration_results['number_store']}")
                    logger.info(f"Store Distribution:")
                    for store_info in iteration_results["list_stores"].split(", "):
                        logger.info(f"  {store_info}")

                    # Update best solution
                    if best_solution is None or actual_cost < best_solution["total_price"]:
                        best_solution = iteration_results
                        logger.info(">>> New best solution found!")

                else:
                    logger.warning("No feasible solution found with the minimum store constraint.")

                return best_solution["sorted_results_df"] if best_solution else None, all_iterations_results

        except Exception as e:
            logger.error(f"Error in compute_pulp_optimization: {str(e)}", exc_info=True)
            return None, None

    def run_milp_optimization(self):
        return self._run_pulp(
            self.filtered_listings_df,
            self.user_wishlist_df,
            self.config["min_store"],
            self.config["find_min_store"],
        )

    # Modified _run_pulp to use the split functions
    @staticmethod
    def _run_pulp(filtered_listings_df, user_wishlist_df, min_store, find_min_store):
        """Main MILP optimization function."""
        try:
            # Setup phase
            setup_results = PurchaseOptimizer._setup_pulp_optimization(filtered_listings_df, user_wishlist_df)

            if any(result is None for result in setup_results):
                return None, None

            filtered_listings_df, unique_cards, unique_stores, costs, total_qty = setup_results

            # Validate minimum store requirement
            if len(unique_stores) < min_store:
                logger.warning(
                    f"Adjusting min_store from {min_store} to {len(unique_stores)} " f"due to available stores"
                )
                min_store = len(unique_stores)

            # Compute phase
            return PurchaseOptimizer._compute_pulp_optimization(
                filtered_listings_df,
                user_wishlist_df,
                unique_cards,
                unique_stores,
                costs,
                total_qty,
                min_store,
                find_min_store,
            )

        except Exception as e:
            logger.error("_run_pulp: %s", str(e))
            logger.error("DataFrame columns: %s", filtered_listings_df.columns.tolist())
            raise

    @staticmethod
    def _setup_prob(costs, unique_cards, unique_stores, user_wishlist, min_store):
        """Setup MILP problem with proper store constraints"""
        # Add validation for store count
        if len(unique_stores) < min_store:
            logger.warning(f"Adjusting min_store from {min_store} to {len(unique_stores)} due to available stores")
            min_store = len(unique_stores)

        prob = pulp.LpProblem("MTGCardOptimization", pulp.LpMinimize)

        # Decision variables
        buy_vars = pulp.LpVariable.dicts("Buy", (unique_cards, unique_stores), 0, 1, pulp.LpBinary)
        store_vars = pulp.LpVariable.dicts("Store", unique_stores, 0, 1, pulp.LpBinary)

        # Calculate total possible cost for normalization
        total_possible_cost = sum(min(costs[card].values()) for card in unique_cards)

        # Calculate weights for multi-objective
        cost_weight = 0.7  # 70% weight on cost
        store_weight = 0.3  # 30% weight on number of stores

        # Objective function combining normalized cost and store count
        prob += cost_weight * pulp.lpSum(
            buy_vars[card][store] * costs[card][store] for card in unique_cards for store in unique_stores
        ) / total_possible_cost + store_weight * pulp.lpSum(store_vars[store] for store in unique_stores) / len(
            unique_stores
        )

        # Constraints

        # 1. Required quantity constraint for each card
        for card in unique_cards:
            required_quantity = user_wishlist[user_wishlist["name"] == card]["quantity"].iloc[0]
            prob += (
                pulp.lpSum([buy_vars[card][store] for store in unique_stores]) == required_quantity,
                f"Required_quantity_{card}",
            )

        # 2. Strong store usage constraint
        # If we buy from a store, its store_var must be 1
        M = len(unique_cards)  # Big-M value
        for store in unique_stores:
            # If we buy any card from a store, that store must be used
            prob += (
                pulp.lpSum(buy_vars[card][store] for card in unique_cards) <= M * store_vars[store],
                f"Store_usage_{store}",
            )
            # If we don't buy any cards, store must not be used
            prob += (
                pulp.lpSum(buy_vars[card][store] for card in unique_cards) >= store_vars[store],
                f"Store_usage_min_{store}",
            )

        # 3. Store count constraints
        # Minimum store constraint
        if min_store > 0:
            prob += (pulp.lpSum(store_vars[store] for store in unique_stores) >= min_store, "Min_stores")

        # Maximum store constraint (using current store count)
        prob += (
            pulp.lpSum(store_vars[store] for store in unique_stores) == min_store,
            "Exact_stores",  # Force exactly min_store stores
        )

        # Solve the problem
        prob.solve(pulp.PULP_CBC_CMD(msg=False))

        return prob, buy_vars

    @staticmethod
    def _process_result(buy_vars, costs, filtered_listings_df) -> Dict:
        Total_price = 0.0
        results = []
        total_card_nbr = 0

        found_cards = set()
        all_cards = set(card for card, _ in buy_vars.items())
        store_usage = defaultdict(int)

        for card, store_dict in buy_vars.items():
            for store, var in store_dict.items():
                quantity = var.value()
                if quantity > 0:
                    weighted_price = round(costs[card][store], 2)
                    if weighted_price != 10000:  # Only include cards in solution
                        # Find matching cards using weighted_price instead of price
                        matching_cards = filtered_listings_df[
                            (filtered_listings_df["name"] == card)
                            & (filtered_listings_df["site_name"] == store)
                            & (filtered_listings_df["weighted_price"].round(2) == weighted_price)
                        ]

                        if matching_cards.empty:
                            # If no exact match, try finding the closest weighted_price match
                            potential_matches = filtered_listings_df[
                                (filtered_listings_df["name"] == card) & (filtered_listings_df["site_name"] == store)
                            ]

                            if not potential_matches.empty:
                                # Find the card with the closest weighted_price
                                closest_match_idx = (
                                    (potential_matches["weighted_price"] - weighted_price).abs().idxmin()
                                )
                                matching_cards = filtered_listings_df.loc[[closest_match_idx]]
                                logger.info(
                                    f"Using closest price match for {card} at {store}: "
                                    f"Expected weighted_price: {weighted_price}, "
                                    f"Found weighted_price: {matching_cards.iloc[0]['weighted_price']:.2f}"
                                )
                            else:
                                logger.warning(f"Could not find any matches for {card} at {store}")
                                continue

                        card_data = matching_cards.iloc[0]
                        actual_price = float(card_data["price"])

                        card_store_total_price = quantity * actual_price
                        found_cards.add(card)
                        Total_price += card_store_total_price
                        total_card_nbr += quantity
                        store_usage[store] += 1

                        if "variant_id" not in card_data or card_data.get("variant_id") is None:
                            logger.warning(f"Card missing variant_id during optimization: {card} at {store}")

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

        results_df = pd.DataFrame(results)
        sorted_results_df = results_df.sort_values(by=["site_name", "name"])
        sorted_results_df.reset_index(drop=True, inplace=True)
        missing_cards = sorted(list(all_cards - found_cards))

        # Generate store distribution string
        store_usage_str = ", ".join(f"{store}: {count}" for store, count in store_usage.items())
        real_total_qty = sum(result["quantity"] for result in results)
        # Group cards by store
        stores_data = defaultdict(list)
        for card in results:
            stores_data[card["site_name"]].append(card)

        stores = [
            {"site_name": store, "site_id": cards[0]["site_id"], "cards": cards} for store, cards in stores_data.items()
        ]

        return {
            "nbr_card_in_solution": int(total_card_nbr),
            "total_price": float(Total_price),
            "number_store": len(stores),
            "list_stores": store_usage_str,
            "stores": stores,
            "sorted_results_df": sorted_results_df,  # Keep as DataFrame
            "missing_cards": missing_cards,
            "missing_cards_count": len(missing_cards),
            "total_qty": real_total_qty,
        }

    def run_nsga_ii_optimization(self, milp_solution=None):
        return self._run_nsga_ii(self.filtered_listings_df, self.user_wishlist_df, self.config, milp_solution)

    def _run_nsga_ii(self, filtered_listings_df, user_wishlist_df, config, milp_solution=None):
        """Enhanced NSGA-II implementation with better solution tracking"""

        # Initialize parameters
        NGEN = 50
        POP_SIZE = 300
        TOURNAMENT_SIZE = 3
        CXPB = 0.85
        MUTPB = 0.15
        ELITE_SIZE = 30

        toolbox = PurchaseOptimizer._initialize_toolbox(filtered_listings_df, user_wishlist_df, config)

        # Initialize population
        if milp_solution:
            logger.info("Integrating MILP solution into initial population")
            pop = PurchaseOptimizer._initialize_population_with_milp(
                POP_SIZE, filtered_listings_df, user_wishlist_df, milp_solution
            )
            if pop is None:
                pop = toolbox.population(n=POP_SIZE)
        else:
            pop = toolbox.population(n=POP_SIZE)

        if not pop:
            logger.error("Failed to initialize population")
            return None

        # Initialize tracking variables
        best_solution = None
        best_fitness = float("inf")
        generations_without_improvement = 0
        archive = tools.ParetoFront()

        # Evaluate initial population
        fitnesses = [toolbox.evaluate(ind) for ind in pop]
        for ind, fit in zip(pop, fitnesses):
            ind.fitness.values = fit
            # Track best solution
            if fit[1] >= 0.999 and fit[0] < best_fitness:  # Complete solution with better cost
                best_fitness = fit[0]
                best_solution = toolbox.clone(ind)
                logger.info(f"New best solution found: ${fit[0]:.2f}")

        # Update archive with initial population
        archive.update(pop)

        # Evolution loop
        for gen in range(NGEN):
            offspring = []
            elite = []

            # Identify elite solutions (complete solutions with best fitness)
            complete_solutions = [ind for ind in pop if ind.fitness.values[1] >= 0.999]
            if complete_solutions:
                elite = sorted(complete_solutions, key=lambda x: x.fitness.values[0])[:ELITE_SIZE]

            # Fill remaining elite slots with best incomplete solutions if needed
            if len(elite) < ELITE_SIZE:
                remaining_slots = ELITE_SIZE - len(elite)
                incomplete_solutions = sorted(
                    [ind for ind in pop if ind not in elite],
                    key=lambda x: (-x.fitness.values[1], x.fitness.values[0]),  # Sort by completeness then cost
                )
                elite.extend(incomplete_solutions[:remaining_slots])

            # Generate offspring
            while len(offspring) < POP_SIZE - len(elite):
                # Select parents with bias towards complete solutions
                if complete_solutions and random.random() < 0.7:
                    parent1 = random.choice(complete_solutions)
                    parent2 = tools.selTournament(
                        [ind for ind in pop if ind != parent1], k=1, tournsize=TOURNAMENT_SIZE
                    )[0]
                else:
                    parent1, parent2 = tools.selTournament(pop, k=2, tournsize=TOURNAMENT_SIZE)

                # Crossover
                if random.random() < CXPB:
                    child1, child2 = toolbox.mate(toolbox.clone(parent1), toolbox.clone(parent2))
                    # Mutation
                    if random.random() < MUTPB:
                        child1 = toolbox.mutate(child1)[0]
                    if random.random() < MUTPB:
                        child2 = toolbox.mutate(child2)[0]

                    del child1.fitness.values, child2.fitness.values
                    offspring.extend([child1, child2])

            # Evaluate offspring
            for ind in offspring:
                ind.fitness.values = toolbox.evaluate(ind)
                # Track best solution
                if (
                    ind.fitness.values[1] >= 0.999 and ind.fitness.values[0] < best_fitness  # Complete solution
                ):  # Better cost
                    best_fitness = ind.fitness.values[0]
                    best_solution = toolbox.clone(ind)
                    generations_without_improvement = 0
                    logger.info(
                        f"Gen {gen}: New best solution found: "
                        f"${ind.fitness.values[0]:.2f}, "
                        f"Completeness: {ind.fitness.values[1]:.2%}"
                    )

            # Update population and archive
            pop = elite + offspring[: (POP_SIZE - len(elite))]
            archive.update(pop)

            # Log progress
            complete_in_pop = sum(1 for ind in pop if ind.fitness.values[1] >= 0.999)
            complete_in_archive = sum(1 for ind in archive if ind.fitness.values[1] >= 0.999)
            current_best_cost = min(
                (ind.fitness.values[0] for ind in pop if ind.fitness.values[1] >= 0.999), default=float("inf")
            )

            if gen % 5 == 0:
                logger.info(f"Gen {gen}:")
                logger.info(f"  Complete solutions in population: {complete_in_pop}")
                logger.info(f"  Complete solutions in archive: {complete_in_archive}")
                logger.info(f"  Best cost: ${current_best_cost:.2f}")
                logger.info(f"  Generations without improvement: {generations_without_improvement}")

            # Convergence check
            if current_best_cost >= best_fitness:
                generations_without_improvement += 1
            else:
                generations_without_improvement = 0

            if generations_without_improvement >= 15:
                logger.info(f"Converged after {gen} generations without improvement")
                break

        # Modified solution extraction and standardization
        if best_solution is not None:
            logger.info(f"Final NSGA-II Solution:")
            logger.info(f"Cost: ${best_solution.fitness.values[0]:.2f}")
            logger.info(f"Completeness: {best_solution.fitness.values[1]:.2%}")

            # Extract and standardize best solution
            standardized_solution = self._standardize_nsga_solution(
                best_solution, filtered_listings_df, user_wishlist_df
            )

            if standardized_solution:
                # Extract and standardize all solutions in the archive
                standardized_iterations = []
                for ind in sorted(archive, key=lambda x: x.fitness.values[0]):
                    iteration_solution = self._standardize_nsga_solution(ind, filtered_listings_df, user_wishlist_df)
                    if iteration_solution:
                        standardized_iterations.append(iteration_solution)

                logger.info(f"Found {len(standardized_iterations)} complete solutions in archive")
                return standardized_solution, standardized_iterations

        logger.warning("No complete solutions found in NSGA-II")
        return None, None

    @staticmethod
    def _initialize_toolbox(filtered_listings_df, user_wishlist_df, config):
        toolbox = base.Toolbox()
        toolbox.register("attr_idx", random.randint, 0, len(filtered_listings_df) - 1)
        toolbox.register(
            "individual",
            tools.initRepeat,
            creator.Individual,
            toolbox.attr_idx,
            n=sum(user_wishlist_df["quantity"]),
        )
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        toolbox.register(
            "evaluate",
            PurchaseOptimizer._evaluate_solution_wrapper(filtered_listings_df, user_wishlist_df, config),
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
            point = random.randint(1, len(ind1) - 1)
            ind1[point:], ind2[point:] = ind2[point:], ind1[point:]
        return ind1, ind2

    @staticmethod
    def _initialize_individual(filtered_listings_df, user_wishlist_df):
        """Initialize an individual with the correct length based on wishlist quantities"""
        individual = []
        not_present = set()

        expected_length = sum(user_wishlist_df["quantity"])

        # Debug information
        # logger.info(f"Available cards in filtered_listings_df: {filtered_listings_df['name'].unique().tolist()}")
        # logger.info(f"Requested cards in wishlist: {user_wishlist_df['name'].tolist()}")

        for _, card in user_wishlist_df.iterrows():
            card_name = card["name"]
            required_quantity = int(card.get("quantity", 1))

            # Case-insensitive search for card name
            available_options = filtered_listings_df[filtered_listings_df["name"].str.lower() == card_name.lower()]

            if not available_options.empty:
                # Add the same card multiple times based on required quantity
                for _ in range(required_quantity):
                    selected_option = available_options.sample(n=1)
                    individual.append(selected_option.index.item())
            else:
                # Debug information for missing cards
                logger.info(f"Card '{card_name}' not found. Available cards containing this name:")
                similar_cards = filtered_listings_df[
                    filtered_listings_df["name"].str.lower().str.contains(card_name.lower(), regex=False)
                ]
                if not similar_cards.empty:
                    logger.debug(f"Similar cards found: {similar_cards['name'].unique().tolist()}")
                not_present.add(card_name)

        if not_present:
            logger.info(f"Cards not found in filtered listings: {list(not_present)}")

        if len(individual) != expected_length:
            raise ValueError(f"Invalid individual length: {len(individual)} != {expected_length}")

        return creator.Individual(individual)

    @staticmethod
    def _initialize_population_with_milp(n, filtered_listings_df, user_wishlist_df, milp_solution):
        """
        Initialize genetic algorithm population using MILP solution.

        Args:
            n (int): Population size
            filtered_listings_df (pd.DataFrame): DataFrame with all card listings
            user_wishlist_df (pd.DataFrame): DataFrame with user's card requirements
            milp_solution (list): Solution from MILP optimization

        Returns:
            list: Initial population for genetic algorithm
        """
        try:
            elite_size = max(1, n // 10)
            # Convert MILP solution to valid indices
            milp_indices = PurchaseOptimizer._convert_solution_to_indices(
                solution=milp_solution, filtered_listings_df=filtered_listings_df
            )

            # Create population
            population = []

            if milp_indices is None:
                logger.warning("Failed to convert MILP solution, using random population")
                return PurchaseOptimizer._initialize_random_population(n, filtered_listings_df, user_wishlist_df)

            # Validate length matches requirements
            expected_length = sum(user_wishlist_df["quantity"])
            if len(milp_indices) != expected_length:
                logger.warning(
                    f"MILP solution length {len(milp_indices)} does not match " f"required length {expected_length}"
                )
                return PurchaseOptimizer._initialize_random_population(n, filtered_listings_df, user_wishlist_df)

            # Add MILP solution as first individual
            for _ in range(elite_size):
                # Create slight variations of MILP solution
                variant = creator.Individual(milp_indices)
                if random.random() < 0.5:  # 50% chance to mutate
                    variant = PurchaseOptimizer._custom_mutation(
                        variant, filtered_listings_df, user_wishlist_df, indpb=0.1  # Low mutation rate for variants
                    )[0]
                population.append(variant)

            remaining = n - elite_size
            # Create remaining individuals
            milp_stores = set(x["site_name"] for x in milp_solution)
            for _ in range(remaining):
                try:
                    new_ind = PurchaseOptimizer._initialize_individual_biased(
                        filtered_listings_df, user_wishlist_df, milp_stores
                    )
                    if new_ind is not None:
                        population.append(new_ind)

                except Exception as e:
                    logger.warning(f"Failed to initialize individual: {str(e)}")
                    continue

            if len(population) < n:
                logger.warning(f"Could only create {len(population)} valid individuals " f"out of requested {n}")
            return population if population else None

        except Exception as e:
            logger.error(f"Error in _initialize_population_with_milp: {str(e)}")
            return None

    @staticmethod
    def _initialize_individual_biased(filtered_listings_df, user_wishlist_df, milp_store_choices):
        """Initialize an individual with bias towards MILP store choices.

        Args:
            filtered_listings_df (pd.DataFrame): DataFrame with all card listings
            user_wishlist_df (pd.DataFrame): DataFrame with user's card requirements
            milp_store_choices (set): Set of store names from MILP solution

        Returns:
            creator.Individual: A new individual biased towards MILP store choices
        """
        individual = []
        not_present = set()

        expected_length = sum(user_wishlist_df["quantity"])

        for _, card in user_wishlist_df.iterrows():
            card_name = card["name"]
            required_quantity = int(card.get("quantity", 1))

            # First try MILP store choices
            preferred_options = filtered_listings_df[
                (filtered_listings_df["name"].str.lower() == card_name.lower())
                & (filtered_listings_df["site_name"].isin(milp_store_choices))
            ]

            # If no options in preferred stores, fall back to all stores
            if preferred_options.empty:
                available_options = filtered_listings_df[filtered_listings_df["name"].str.lower() == card_name.lower()]
            else:
                available_options = preferred_options

            if not available_options.empty:
                # Add the same card multiple times based on required quantity
                for _ in range(required_quantity):
                    # Bias towards better quality/price ratio when selecting
                    weights = [
                        QUALITY_WEIGHTS.get(r["quality"], 0) / (float(r["price"]) + 0.1)
                        for _, r in available_options.iterrows()
                    ]
                    selected_option = available_options.sample(n=1, weights=weights)
                    individual.append(selected_option.index.item())
            else:
                not_present.add(card_name)

        if not_present:
            logger.debug(f"Cards not found in filtered listings: {list(not_present)}")

        if len(individual) != expected_length:
            raise ValueError(f"Invalid individual length: {len(individual)} != {expected_length}")

        return creator.Individual(individual)

    @staticmethod
    def _initialize_random_population(n, filtered_listings_df, user_wishlist_df):
        """Create completely random initial population."""
        population = []
        for _ in range(n):
            try:
                individual = PurchaseOptimizer._initialize_individual(filtered_listings_df, user_wishlist_df)
                if individual is not None:
                    population.append(individual)
            except Exception as e:
                logger.warning(f"Failed to initialize random individual: {str(e)}")
                continue
        return population if population else None

    @staticmethod
    def _custom_mutation(individual, filtered_listings_df, user_wishlist_df, indpb=0.05):
        for i in range(len(individual)):
            if random.random() < indpb:
                card_name = user_wishlist_df.iloc[i % len(user_wishlist_df)]["name"]
                # Get all available options for this card
                available_options = filtered_listings_df[filtered_listings_df["name"] == card_name]
                if not available_options.empty:
                    # Choose a random option weighted by quality and inverse price
                    weights = [
                        QUALITY_WEIGHTS.get(r["quality"], 0) / (float(r["price"]) + 0.1)
                        for _, r in available_options.iterrows()
                    ]
                    individual[i] = random.choices(available_options.index, weights=weights, k=1)[0]
        return (individual,)

    @staticmethod
    def _evaluate_solution_wrapper(filtered_listings_df, user_wishlist_df, config):
        """Revised evaluation function with better handling of incomplete solutions."""

        def evaluate_solution(individual):
            solution_data = {}
            stores_used = set()
            total_cost = 0
            quality_scores = []

            # Track cards and quantities found
            required_cards = {row["name"]: row["quantity"] for _, row in user_wishlist_df.iterrows()}
            found_cards = defaultdict(int)

            # Process each card in solution
            for idx in individual:
                if idx not in filtered_listings_df.index:
                    continue

                card = filtered_listings_df.loc[idx]
                card_name = card["name"]

                # Only count if we still need this card
                if found_cards[card_name] < required_cards.get(card_name, 0):
                    found_cards[card_name] += 1
                    stores_used.add(card["site_name"])

                    # Calculate adjusted price with language penalty
                    language_penalty = LANGUAGE_WEIGHTS.get(
                        card.get("language", "Unknown"), LANGUAGE_WEIGHTS["default"]
                    )
                    adjusted_price = float(card["price"]) * language_penalty
                    total_cost += adjusted_price

                    # Calculate quality score adjusted by language
                    quality = card.get("quality", "DMG")
                    max_weight = max(QUALITY_WEIGHTS.values())
                    base_quality_score = 1 - (QUALITY_WEIGHTS[quality] - 1) / (max_weight - 1)
                    adjusted_quality_score = base_quality_score / language_penalty
                    quality_scores.append(adjusted_quality_score)

                    solution_data[card_name] = card.to_dict()

            # Calculate core metrics
            total_cards_needed = sum(required_cards.values())
            total_cards_found = sum(found_cards.values())
            completeness = total_cards_found / total_cards_needed if total_cards_needed > 0 else 0
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            store_count = len(stores_used)

            # Apply store count constraints
            if store_count > config.get("max_store", float("inf")):
                store_penalty = (store_count - config["max_store"]) * 1000
            else:
                store_penalty = 0

            # Calculate cost with completeness penalty
            if completeness < 1.0:
                # Use exponential penalty for incompleteness
                completeness_penalty = (1 - completeness) * total_cards_needed * 100
                adjusted_cost = total_cost + completeness_penalty
            else:
                adjusted_cost = total_cost

            # Add store penalty to cost
            final_cost = adjusted_cost + store_penalty

            return (
                final_cost,  # Cost objective (with penalties)
                completeness,  # Completeness objective
                avg_quality,  # Quality objective
                float(store_count),  # Store count objective
            )

        return evaluate_solution

    @staticmethod
    def _calculate_average_quality(solution_data):
        """Calculate normalized quality score (0-1, higher is better)"""
        quality_weights = QUALITY_WEIGHTS  # Use constant from app.constants
        quality_scores = []

        for card in solution_data:
            quality = card.get("quality", "DMG")
            # Convert quality to numeric score (1 is best, 0 is worst)
            max_weight = max(quality_weights.values())
            score = 1 - (quality_weights.get(quality, max_weight) - 1) / (max_weight - 1)
            quality_scores.append(score)

        return sum(quality_scores) / len(quality_scores) if quality_scores else 0

    def _extract_purchasing_plan(self, solution, filtered_listings_df, user_wishlist_df):
        """
        Extract purchasing plan from various solution formats.

        Args:
            solution: Can be either:
                - NSGA-II individual (has 'fitness' attribute and is list of indices)
                - List of dictionaries with card details (MILP format)
            filtered_listings_df: DataFrame with all available cards
            user_wishlist_df: DataFrame with required cards

        Returns:
            list: List of dictionaries with purchasing details
        """
        try:
            # Handle NSGA-II solution
            if hasattr(solution, "fitness"):
                return self._standardize_nsga_solution(solution, filtered_listings_df, user_wishlist_df)

            # Handle MILP solution (already in correct format)
            elif isinstance(solution, list) and all(isinstance(item, dict) for item in solution):
                return self._create_standardized_solution(solution)

            else:
                logger.error(f"Unsupported solution type: {type(solution)}")
                return None

        except Exception as e:
            logger.error(f"Error in _extract_purchasing_plan: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def _cleanup_temporary_columns(df):  # Removed 'self' parameter
        temp_columns = ["Identifier", "weighted_price", "site_info"]  # Added 'site_info' to columns to clean
        for col in temp_columns:
            if col in df.columns:
                df = df.drop(columns=[col])
        return df
