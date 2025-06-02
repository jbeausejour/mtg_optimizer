import logging
import random
from collections import defaultdict
from functools import partial
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import pulp
from pulp import PULP_CBC_CMD
from app.constants import CardLanguage, CardQuality, CardVersion
from app.constants import CurrencyConverter
from app.utils.data_fetcher import ErrorCollector
from deap import algorithms, base, creator, tools

logger = logging.getLogger(__name__)


class PurchaseOptimizer:
    def __init__(self, filtered_listings_df, user_wishlist_df, optimizationConfig):
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
        self.optimizationConfig = optimizationConfig
        self.init_fitness_creator(self.optimizationConfig.weights)

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

        # Check if currency conversion was applied
        self._log_currency_info()
        # logger.info("PurchaseOptimizer initialized with config: %s", self.optimizationConfig)

        self._validate_input_data()

        # Add validation for sites
        unique_sites = filtered_listings_df["site_name"].nunique()
        if unique_sites < self.optimizationConfig.min_store:
            logger.warning(f"Found only {unique_sites} sites, but minimum {self.optimizationConfig.min_store} required")
            # Adjust min_store if needed
            self.optimizationConfig.min_store = min(unique_sites, self.optimizationConfig.min_store)

        if unique_sites < self.optimizationConfig.max_store:
            logger.warning(f"Found only {unique_sites} sites, but minimum {self.optimizationConfig.min_store} required")
            # Adjust min_store if needed
            self.optimizationConfig.max_store = min(unique_sites, self.optimizationConfig.max_store)

        logger.info(f"[Weights] Cost: {self.optimizationConfig.weights.get('cost', 1.0)}")
        logger.info(f"[Weights] Quality: {self.optimizationConfig.weights.get('quality', 1.0)}")
        logger.info(f"[Weights] Availability: {self.optimizationConfig.weights.get('availability', 100.0)}")
        logger.info(f"[Weights] Store Count: {self.optimizationConfig.weights.get('store_count', 0.3)}")
        logger.info(f"Initializing optimizer with {unique_sites} unique sites")

    def _log_currency_info(self):
        """Log information about currency conversion in the dataset"""
        df = self.filtered_listings_df

        # Check if currency conversion columns exist
        if "original_currency" in df.columns and "original_price" in df.columns:
            # Log currency distribution
            currency_stats = (
                df.groupby("original_currency")
                .agg(
                    {
                        "original_price": ["count", "mean", "min", "max"],
                        "price": ["mean", "min", "max"],  # CAD prices after conversion
                    }
                )
                .round(4)
            )

            logger.info("=== CURRENCY CONVERSION SUMMARY ===")
            for currency in currency_stats.index:
                count = currency_stats.loc[currency, ("original_price", "count")]
                orig_avg = currency_stats.loc[currency, ("original_price", "mean")]
                orig_min = currency_stats.loc[currency, ("original_price", "min")]
                orig_max = currency_stats.loc[currency, ("original_price", "max")]
                cad_avg = currency_stats.loc[currency, ("price", "mean")]
                cad_min = currency_stats.loc[currency, ("price", "min")]
                cad_max = currency_stats.loc[currency, ("price", "max")]

                converter = CurrencyConverter()
                symbol = converter.get_currency_symbol(currency)

                logger.info(f"Currency: {currency} ({symbol})")
                logger.info(f"  Items: {count}")
                logger.info(
                    f"  Original prices: {symbol}{orig_min:.2f} - {symbol}{orig_max:.2f} (avg: {symbol}{orig_avg:.2f})"
                )
                logger.info(f"  CAD prices: ${cad_min:.2f} - ${cad_max:.2f} (avg: ${cad_avg:.2f})")

                if currency != "CAD":
                    rate = (
                        currency_stats.loc[currency, ("price", "mean")]
                        / currency_stats.loc[currency, ("original_price", "mean")]
                    )
                    logger.info(f"  Conversion rate used: ~{rate:.4f} (1 {currency} = {rate:.4f} CAD)")

            logger.info("=== END CURRENCY CONVERSION SUMMARY ===")

            # Validate that all prices are now in CAD
            total_items = len(df)
            converted_items = len(df[df["original_currency"] != "CAD"])
            logger.info(f"Currency conversion: {converted_items}/{total_items} items converted to CAD")

        else:
            logger.info("No currency conversion data found - assuming all prices are in CAD (default currency)")

    def init_fitness_creator(self, weights):
        def safe(w, fallback):
            return w if isinstance(w, (int, float)) and w > 0 else fallback

        if not hasattr(creator, "FitnessMulti"):
            creator.create(
                "FitnessMulti",
                base.Fitness,
                weights=(
                    -safe(weights.get("cost"), 1.0),
                    safe(weights.get("quality"), 1.0),
                    safe(weights.get("availability"), 100.0),
                    -safe(weights.get("store_count"), 0.3),
                ),
            )
            logger.info(f"Creating DEAP fitness class with weights: {weights}")
            creator.create("Individual", list, fitness=creator.FitnessMulti)

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

    def run_optimization(self, card_names, optimizationConfig, celery_task=None):
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
            logger.info(
                f"Found {self.filtered_listings_df['site_name'].nunique()}/{optimizationConfig.max_unique_store} unique sites"
            )
            # logger.info(f"Unique sites: {self.filtered_listings_df['site_name'].unique().tolist()}")

            final_result = None
            best_solution_records = None
            if optimizationConfig.milp_strat or optimizationConfig.hybrid_strat:
                logger.info("Running MILP optimization...")

                if celery_task:
                    celery_task.progress += 5
                    # progress = 60 --> 65
                    celery_task.update_state(
                        state="PROCESSING",
                        meta={
                            "status": "Running MILP Optimization",
                            "progress": f"{celery_task.progress:.2f}",
                            "details": {"step": "MILP"},
                        },
                    )
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
                            solution["source"] = "milp"
                            solution["strategy"] = "milp"
                            milp_iterations.append(solution)

                    milp_result = {
                        "status": "success",
                        "best_solution": best_milp_solution_found,
                        "iterations": milp_iterations,
                        "type": "milp",
                    }
                    final_result = milp_result
                    if not optimizationConfig.hybrid_strat:
                        PurchaseOptimizer.print_detailed_solution_summary(milp_result, len(card_names))
                        # formatted_summary = self.format_optimization_summary(milp_result)
                        # logger.info(f"Summary of Milp optimization:")
                        # logger.info(f"{formatted_summary}")
                else:
                    logger.warning("MILP optimization returned no results")

            if optimizationConfig.nsga_strat or optimizationConfig.hybrid_strat:
                logger.info("Running NSGA-II optimization...")
                milp_solution = None

                if celery_task:
                    celery_task.progress += 5
                    # progress = 65 --> 70
                    celery_task.update_state(
                        state="PROCESSING",
                        meta={
                            "status": "Running NSGA-II Optimization",
                            "progress": f"{celery_task.progress:.2f}",
                            "details": {"step": "NSGA-II"},
                        },
                    )

                if optimizationConfig.hybrid_strat and milp_result and milp_result.get("best_solution"):
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
                    for iteration in nsga_iterations:
                        iteration["source"] = "nsga"
                        iteration["strategy"] = "nsga"

                    # For hybrid strategy, compare and select the better solution
                    if optimizationConfig.hybrid_strat and milp_result:
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
                PurchaseOptimizer.print_detailed_solution_summary(final_result, len(card_names))
                # formatted_summary = self.format_optimization_summary(final_result)
                # logger.info(f"Summary of optimization:")
                # for item in formatted_summary:
                #     logger.info(item)
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

    # def format_optimization_summary(self, final_result):
    #     """Format optimization results in a human-readable way"""
    #     try:
    #         # Extract solution data
    #         best_solution = final_result.get("best_solution", {})
    #         iterations = final_result.get("iterations", [])
    #         opt_type = final_result.get("type", "unknown")

    #         # Get the actual card data from the standardized format
    #         if isinstance(best_solution, dict):
    #             # If it's the standardized format, get the stores data
    #             stores = best_solution.get("stores", [])
    #             cards_data = []
    #             for store in stores:
    #                 cards_data.extend(store.get("cards", []))

    #             # Get pre-calculated statistics
    #             total_price = best_solution.get("total_price", 0)
    #             cards_found = best_solution.get("nbr_card_in_solution", 0)
    #             store_count = best_solution.get("number_store", 0)
    #             missing_count = best_solution.get("missing_cards_count", 0)

    #         elif isinstance(best_solution, pd.DataFrame):
    #             # Handle DataFrame format
    #             cards_data = best_solution.to_dict("records")
    #             total_price = sum(float(card["price"]) * int(card["quantity"]) for card in cards_data)
    #             cards_found = len(cards_data)
    #             store_count = len(set(card["site_name"] for card in cards_data))
    #             missing_count = 0  # Would need additional context to calculate

    #         else:
    #             # Handle direct list format
    #             cards_data = best_solution if isinstance(best_solution, list) else []
    #             total_price = sum(float(card["price"]) * int(card["quantity"]) for card in cards_data)
    #             cards_found = len(cards_data)
    #             store_count = len(set(card["site_name"] for card in cards_data))
    #             missing_count = 0

    #         # Calculate quality distribution
    #         quality_counts = defaultdict(int)
    #         total_cards = 0
    #         for card in cards_data:
    #             quantity = int(card.get("quantity", 1))
    #             quality = card.get("quality", "Unknown")
    #             quality_counts[quality] += quantity
    #             total_cards += quantity

    #         # Format the summary
    #         summary = [
    #             "Final Optimization Results:",
    #             f"{'='*50}",
    #             f"Optimization Type:  {opt_type}",
    #             f"Cards Found:        {cards_found} cards",
    #             f"Missing Cards:      {missing_count} cards",
    #             f"Total Cost:         ${total_price:.2f}",
    #             f"Stores Used:        {store_count} stores",
    #             f"Solutions Tried:    {len(iterations)}",
    #             "",
    #             "Quality Distribution:",
    #             "-" * 50,
    #         ]

    #         if total_cards > 0:
    #             for quality, count in sorted(quality_counts.items()):
    #                 percentage = (count / total_cards) * 100
    #                 summary.append(f"{quality:<15} {count:>3} cards ({percentage:>5.1f}%)")
    #         else:
    #             summary.append("No cards in solution")

    #         # Add store distribution if available
    #         summary.append("")
    #         summary.append("Store Distribution")
    #         summary.append("-" * 50)
    #         if isinstance(best_solution, dict) and "list_stores" in best_solution:
    #             for store in best_solution["list_stores"].split(", "):
    #                 summary.append(store)

    #         return summary

    #     except Exception as e:
    #         logger.error(f"Error formatting optimization summary: {str(e)}", exc_info=True)
    #         return (
    #             f"Optimization completed ({opt_type})\n"
    #             f"Cards found: {cards_found}\n"
    #             f"Total cost: ${total_price:.2f}"
    #         )
    @staticmethod
    def _extract_cards_data(result):
        """Extract card list and metadata from a variety of result formats."""
        if isinstance(result, dict) and "best_solution" in result:
            result = result["best_solution"]

        if isinstance(result, dict):
            if "stores" in result:
                cards = [card for store in result["stores"] if "cards" in store for card in store["cards"]]
            elif "sorted_results_df" in result and isinstance(result["sorted_results_df"], pd.DataFrame):
                cards = result["sorted_results_df"].to_dict("records")
            else:
                cards = []
            total = float(result.get("total_price", 0))
            store_count = int(result.get("number_store", 0))
            missing = int(result.get("missing_cards_count", 0))
            store_names = result.get("list_stores", "").split(", ") if result.get("list_stores") else []
            return cards, total, store_count, missing, store_names

        elif isinstance(result, pd.DataFrame):
            cards = result.to_dict("records")
            total = sum(float(c["price"]) * int(c["quantity"]) for c in cards)
            store_count = len(set(c.get("site_name", "unknown") for c in cards))
            return cards, total, store_count, 0, []

        elif isinstance(result, list):
            cards = result
            total = sum(float(c["price"]) * int(c["quantity"]) for c in cards)
            store_count = len(set(c.get("site_name", "unknown") for c in cards))
            return cards, total, store_count, 0, []

        return [], 0.0, 0, 0, []

    @staticmethod
    def print_summary(
        cards, total, store_count, missing, total_qty, opt_type="unknown", iterations=0, store_names=None
    ):
        logger.info("=" * 60)
        logger.info("🧠 Optimization Summary")
        logger.info("=" * 60)

        logger.info(
            f"Cards Found:     {len(cards)}/{total_qty}" if total_qty else f"Cards Found:     {len(cards)} cards"
        )
        logger.info(f"Total Cost:      ${total:.2f}")
        logger.info(f"Stores Used:     {store_count}")
        logger.info(f"Missing Cards:   {missing}")
        logger.info(f"Optimization Type: {opt_type}")
        logger.info(f"Solutions Tried: {iterations}")
        logger.info("")

        quality_counts = defaultdict(int)
        language_counts = defaultdict(int)
        total_card_instances = 0

        for card in cards:
            try:
                qty = int(card.get("quantity", 1))
                quality = card.get("quality", "Unknown")
                lang = card.get("language", "Unknown")
                quality_counts[quality] += qty
                language_counts[lang] += qty
                total_card_instances += qty
            except Exception:
                continue

        if total_card_instances:
            logger.info("📦 Quality Distribution:")
            for q, c in sorted(quality_counts.items()):
                pct = (c / total_card_instances) * 100
                logger.info(f"  {q:<10}: {c} cards ({pct:.1f}%)")

            logger.info("")
            logger.info("🌍 Language Distribution:")
            for l, c in sorted(language_counts.items()):
                pct = (c / total_card_instances) * 100
                logger.info(f"  {l:<10}: {c} cards ({pct:.1f}%)")

        logger.info("")
        logger.info("🏪 Store Distribution:")
        final_names = store_names or sorted(set(card.get("site_name", "Unknown") for card in cards))
        for s in final_names:
            logger.info(f"  {s}")
        logger.info("=" * 60)

    @staticmethod
    def print_detailed_solution_summary(result: dict, total_qty: int = 0):
        try:
            opt_type = (
                result.get("type", "unknown") if isinstance(result, dict) and "best_solution" in result else "direct"
            )
            iterations = len(result.get("iterations", [])) if isinstance(result, dict) else 0
            cards, total, store_count, missing, store_names = PurchaseOptimizer._extract_cards_data(result)
            PurchaseOptimizer.print_summary(
                cards, total, store_count, missing, total_qty, opt_type, iterations, store_names
            )
        except Exception as e:
            logger.exception(f"[Summary] Failed to print optimization summary: {e}")

    # def print_detailed_solution_summary(self, result: dict, total_qty: int = 0):
    #     """Log detailed summary of a solution, whether intermediate or final."""
    #     logger.info("=" * 60)
    #     logger.info("🧠 Optimization Summary")
    #     logger.info("=" * 60)

    #     # Normalize input: full result or just a solution
    #     if isinstance(result, dict) and "best_solution" in result:
    #         best_solution = result.get("best_solution", {})
    #         opt_type = result.get("type", "unknown")
    #         iterations = result.get("iterations", [])
    #     elif isinstance(result, dict):
    #         best_solution = result
    #         opt_type = "direct"
    #         iterations = []
    #     else:
    #         # Handle unexpected types (numpy.int64, etc.)
    #         logger.error(f"Invalid result type for summary: {type(result)}. Expected dict.")
    #         logger.error(f"Result value: {result}")
    #         return

    #     # Handle different solution formats more robustly
    #     cards_data = []
    #     total_price = 0.0
    #     store_count = 0
    #     missing_count = 0

    #     try:
    #         # Format 1: Standardized solution with "stores" key
    #         if isinstance(best_solution, dict) and "stores" in best_solution:
    #             for store in best_solution["stores"]:
    #                 if isinstance(store, dict) and "cards" in store:
    #                     cards_data.extend(store.get("cards", []))
    #             total_price = float(best_solution.get("total_price", 0.0))
    #             store_count = int(best_solution.get("number_store", 0))
    #             missing_count = int(best_solution.get("missing_cards_count", 0))

    #         # Format 2: Solution with DataFrame result
    #         elif isinstance(best_solution, dict) and "sorted_results_df" in best_solution:
    #             df = best_solution["sorted_results_df"]
    #             if isinstance(df, pd.DataFrame) and not df.empty:
    #                 cards_data = df.to_dict("records")
    #                 total_price = float(best_solution.get("total_price", 0.0))
    #                 store_count = int(best_solution.get("number_store", 0))
    #                 missing_count = int(best_solution.get("missing_cards_count", 0))
    #             else:
    #                 # Fallback: extract from dict keys
    #                 total_price = float(best_solution.get("total_price", 0.0))
    #                 store_count = int(best_solution.get("number_store", 0))
    #                 missing_count = int(best_solution.get("missing_cards_count", 0))
    #                 cards_data = []

    #         # Format 3: DataFrame directly
    #         elif isinstance(best_solution, pd.DataFrame):
    #             cards_data = best_solution.to_dict("records")
    #             total_price = sum(float(card.get("price", 0)) * int(card.get("quantity", 1)) for card in cards_data)
    #             store_count = len(set(card.get("site_name", "unknown") for card in cards_data))
    #             missing_count = 0

    #         # Format 4: List of card dictionaries
    #         elif isinstance(best_solution, list):
    #             cards_data = best_solution
    #             total_price = sum(float(card.get("price", 0)) * int(card.get("quantity", 1)) for card in cards_data)
    #             store_count = len(set(card.get("site_name", "unknown") for card in cards_data))
    #             missing_count = 0

    #         # Format 5: Empty or unknown format
    #         else:
    #             logger.warning(f"Unknown solution format: {type(best_solution)}")
    #             if hasattr(best_solution, "keys"):
    #                 logger.warning(f"Available keys: {list(best_solution.keys())}")
    #             return

    #     except Exception as e:
    #         logger.error(f"Error processing solution summary: {str(e)}")
    #         logger.warning(f"Solution type: {type(best_solution)}")
    #         if isinstance(best_solution, dict):
    #             logger.warning(f"Solution keys: {list(best_solution.keys())}")
    #         return

    #     cards_found = len(cards_data)

    #     # Log basic metrics
    #     if total_qty and total_qty > 0:
    #         logger.info(f"Cards Found:     {cards_found}/{total_qty}")
    #     else:
    #         logger.info(f"Cards Found:     {cards_found} cards")
    #     logger.info(f"Total Cost:      ${total_price:.2f}")
    #     logger.info(f"Stores Used:     {store_count}")
    #     logger.info(f"Missing Cards:   {missing_count}")
    #     logger.info(f"Optimization Type: {opt_type}")
    #     logger.info(f"Solutions Tried: {len(iterations)}")
    #     logger.info("")

    #     # Quality and language distribution
    #     if cards_data:
    #         quality_counts = defaultdict(int)
    #         language_counts = defaultdict(int)
    #         total_card_instances = 0

    #         for card in cards_data:
    #             try:
    #                 qty = int(card.get("quantity", 1))
    #                 quality = card.get("quality", "Unknown")
    #                 lang = card.get("language", "Unknown")
    #                 quality_counts[quality] += qty
    #                 language_counts[lang] += qty
    #                 total_card_instances += qty
    #             except (ValueError, TypeError):
    #                 continue

    #         if total_card_instances > 0:
    #             logger.info("📦 Quality Distribution:")
    #             for quality, count in sorted(quality_counts.items()):
    #                 pct = (count / total_card_instances) * 100
    #                 logger.info(f"  {quality:<10}: {count} cards ({pct:.1f}%)")

    #             logger.info("")
    #             logger.info("🌍 Language Distribution:")
    #             for lang, count in sorted(language_counts.items()):
    #                 pct = (count / total_card_instances) * 100
    #                 logger.info(f"  {lang:<10}: {count} cards ({pct:.1f}%)")

    #     # Store distribution
    #     logger.info("")
    #     logger.info("🏪 Store Distribution:")

    #     # Try to get store names from different sources
    #     store_names = []
    #     if isinstance(best_solution, dict):
    #         if "list_stores" in best_solution and best_solution["list_stores"]:
    #             store_names = best_solution["list_stores"].split(", ")
    #         elif "stores" in best_solution:
    #             store_names = [store.get("site_name", "Unknown") for store in best_solution["stores"]]

    #     if not store_names and cards_data:
    #         store_names = sorted(set(card.get("site_name", "Unknown") for card in cards_data))

    #     for store in store_names:
    #         logger.info(f"  {store}")

    #     logger.info("=" * 60)

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
        if "price" in filtered_listings_df.columns:
            filtered_listings_df["price"] = filtered_listings_df["price"].round(2)
        if "weighted_price" in filtered_listings_df.columns:
            filtered_listings_df["weighted_price"] = filtered_listings_df["weighted_price"].round(2)

        for record in solution:
            # Round the price in the record to match DataFrame precision
            record_price = round(float(record.get("price") or record.get("weighted_price", 0.0)), 2)
            price_column = "price" if "price" in record else "weighted_price"

            if price_column not in filtered_listings_df.columns:
                logger.error(f"{price_column} not found in filtered_listings_df. Cannot match record.")
                missing_records.append(record)
                continue
            # Match by name, store, and correct price column
            mask = (
                (filtered_listings_df["name"] == record["name"])
                & (filtered_listings_df["site_name"] == record["site_name"])
                & (filtered_listings_df[price_column] == record_price)
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
                    closest_match = alternate_rows.iloc[(alternate_rows[price_column] - record_price).abs().argmin()]
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
    def _compute_penalized_price(
        row: pd.Series,
        preferences: dict,
        strict: bool,
        quality_weight_map: dict = None,
        language_weight_map: dict = None,
        high_cost: float = 10_000,
    ) -> Tuple[float, float, str]:
        """
        Returns: (final_price, penalty_multiplier, reason)
        """
        explanations = []
        base_price = row.get("price", high_cost)

        # STEP 1: Apply base quality weight using cached lookup
        quality = row.get("quality", "DMG")
        if quality_weight_map and quality in quality_weight_map:
            quality_multiplier = quality_weight_map[quality]
        else:
            # Fallback to direct lookup if cache not available
            quality_multiplier = CardQuality.get_weight(quality)

        weighted_price = base_price * quality_multiplier

        # STEP 2: Apply preference penalties on top
        preference_penalty = 1.0

        for attr in ["language", "version", "quality", "foil"]:
            expected = preferences.get(attr)
            actual = row.get(attr)

            if expected:
                if strict and actual != expected:
                    explanations.append(f"{attr} mismatch (strict): {actual} != {expected}")
                    return high_cost, 1.0, "strict_filter"

                if not strict and actual != expected:
                    if attr == "language":
                        if language_weight_map and actual in language_weight_map:
                            # Use cached language weight
                            attr_penalty = language_weight_map[actual] / language_weight_map.get(expected, 1.0)
                        else:
                            # Fallback to direct calculation
                            attr_penalty = CardLanguage.calculate_language_preference_penalty(actual, expected)
                    elif attr == "version":
                        attr_penalty = CardVersion.calculate_version_preference_penalty(actual, expected)
                    elif attr == "quality":
                        if quality_weight_map and actual in quality_weight_map and expected in quality_weight_map:
                            # Use cached quality weights for preference penalty
                            actual_weight = quality_weight_map[actual]
                            expected_weight = quality_weight_map[expected]
                            attr_penalty = actual_weight / expected_weight if expected_weight > 0 else 1.3
                        else:
                            attr_penalty = CardQuality.calculate_quality_preference_penalty(actual, expected)
                    else:  # foil
                        attr_penalty = 1.3

                    preference_penalty *= attr_penalty
                    explanations.append(
                        f"{attr} preference: {actual} vs wanted {expected} (penalty: {attr_penalty:.1f}x)"
                    )

        final_price = weighted_price * preference_penalty
        return final_price, quality_multiplier * preference_penalty, "; ".join(explanations)

    def _setup_pulp_optimization(self, filtered_listings_df, user_wishlist_df):
        """Set up the MILP optimization problem with data validation and preprocessing."""
        try:
            if user_wishlist_df is None or user_wishlist_df.empty:
                logger.error("user_wishlist_df is None or empty")
                return None, None, None, None, None, None

            if filtered_listings_df is None or filtered_listings_df.empty:
                logger.error("filtered_listings_df is None or empty")
                return None, None, None, None, None, None

            filtered_listings_df = filtered_listings_df.copy()
            filtered_listings_df["site_name"] = filtered_listings_df["site_name"].astype(str)
            filtered_listings_df = filtered_listings_df.loc[:, ~filtered_listings_df.columns.duplicated()]

            unique_cards = user_wishlist_df["name"].unique()
            unique_stores = filtered_listings_df["site_name"].unique()
            total_qty = user_wishlist_df["quantity"].sum()
            high_cost = 10000

            # def compute_weighted(row):
            #     prefs = self.card_preferences.get(row["name"], {})
            #     price, penalty, explanations = self._compute_penalized_price(
            #         row, prefs, self.optimizationConfig.strict_preferences
            #     )
            #     row["weighted_price"] = price
            #     row["penalty_multiplier"] = penalty
            #     row["explanations"] = explanations
            #     return price

            # def compute_weighted_old(row):
            #     # TEMPORARY DEBUG: Skip all penalties to test if this is the issue
            #     price = row.get("price", 10000)
            #     row["weighted_price"] = price
            #     row["penalty_multiplier"] = 1.0
            #     row["explanations"] = "debug_mode_no_penalties"
            #     return price
            # Compute penalized price
            # filtered_listings_df["weighted_price"] = filtered_listings_df.apply(compute_weighted, axis=1)

            # VECTORIZED APPROACH: Compute base quality weights
            quality_weights = filtered_listings_df["quality"].map(CardQuality.get_weight)
            base_weighted_price = filtered_listings_df["price"] * quality_weights

            # Initialize penalty tracking
            filtered_listings_df["penalty_multiplier"] = 1.0
            filtered_listings_df["penalty_explanation"] = ""
            filtered_listings_df["preference_applied"] = False

            cards_with_prefs = set(self.card_preferences.keys())
            mask_has_prefs = filtered_listings_df["name"].isin(cards_with_prefs)

            # For cards without preferences: use simple quality weighting (vectorized)
            simple_mask = ~mask_has_prefs
            filtered_listings_df.loc[simple_mask, "weighted_price"] = base_weighted_price[simple_mask]
            filtered_listings_df.loc[simple_mask, "penalty_explanation"] = "No user preferences defined"

            if mask_has_prefs.any():
                pref_df = filtered_listings_df[mask_has_prefs].copy()
                # Store results for batch update
                weighted_prices = []
                penalties = []
                explanations = []

                def compute_with_preferences(row):
                    """Only for rows that need preference processing"""
                    prefs = self.card_preferences[row["name"]]  # We know it exists
                    price, penalty, explanation = self._compute_penalized_price(
                        row, prefs, self.optimizationConfig.strict_preferences, high_cost=high_cost
                    )
                    weighted_prices.append(price)
                    penalties.append(penalty)
                    explanations.append(explanation)
                    return price

                # Apply detailed calculation only to subset that needs it
                pref_df.apply(compute_with_preferences, axis=1)

                # Batch update the main DataFrame
                filtered_listings_df.loc[mask_has_prefs, "weighted_price"] = weighted_prices
                filtered_listings_df.loc[mask_has_prefs, "penalty_multiplier"] = penalties
                filtered_listings_df.loc[mask_has_prefs, "penalty_explanation"] = explanations
                filtered_listings_df.loc[mask_has_prefs, "preference_applied"] = True

                logger.info(f"Vectorized: {simple_mask.sum()} cards, Complex: {mask_has_prefs.sum()} cards")
            else:
                logger.info(f"All {len(filtered_listings_df)} cards processed with vectorized approach")

            # Log penalty statistics for all processed cards
            self._log_penalty_statistics(filtered_listings_df, mask_has_prefs)

            # Create cost matrix
            raw_costs = {}
            enriched_costs = defaultdict(dict)

            for card in unique_cards:
                for store in unique_stores:
                    rows = filtered_listings_df[
                        (filtered_listings_df["name"] == card) & (filtered_listings_df["site_name"] == store)
                    ]
                    if rows.empty:
                        continue
                    best = rows.sort_values("weighted_price").iloc[0]
                    weighted_price = best["weighted_price"]

                    if card not in raw_costs:
                        raw_costs[card] = {}  # ✅ Fixes KeyError
                    raw_costs[card][store] = weighted_price

                    enriched = best.to_dict()
                    enriched["weighted_price"] = weighted_price
                    enriched["available_quantity"] = best.get("quantity", 1.0)

                    norm_quality = CardQuality.normalize(best.get("quality", "DMG"))
                    max_q = max(CardQuality.get_weight(q.value) for q in CardQuality)
                    enriched["quality_score"] = 1 - (CardQuality.get_weight(norm_quality) - 1) / (max_q - 1)

                    enriched_costs[card][store] = enriched

            for card in unique_cards:
                if card not in raw_costs:
                    logger.warning(f"[COSTS] raw_costs missing card: {card}")
                else:
                    missing_stores = [store for store in unique_stores if store not in raw_costs[card]]
                    if len(missing_stores) == len(unique_stores):
                        logger.warning(f"[COSTS] No stores recorded for card: {card}")
            # Validate that each card has at least one viable store
            for card in unique_cards:
                card_rows = filtered_listings_df[filtered_listings_df["name"] == card]
                if card_rows.empty:
                    logger.warning(f"[FILTER] No listings left for card '{card}' after filtering.")
                else:
                    logger.info(
                        f"[FILTER] Listings for '{card}': {len(card_rows)} entries across {card_rows['site_name'].nunique()} stores."
                    )
                if all(price >= high_cost for price in raw_costs[card].values()):
                    logger.warning(f"[CRITICAL] No viable listings for card '{card}' after filtering.")

            return filtered_listings_df, unique_cards, unique_stores, raw_costs, enriched_costs, total_qty

        except Exception as e:
            logger.error(f"Error in setup_pulp_optimization: {str(e)}", exc_info=True)
            return None, None, None, None, None, None, None

    def _log_penalty_statistics(self, df, preference_mask):
        """Log detailed statistics about penalties applied"""
        pref_df = df[preference_mask]

        if pref_df.empty:
            return

        logger.info("=" * 60)
        logger.info("🔍 PENALTY ANALYSIS")
        logger.info("=" * 60)

        # Overall penalty statistics
        avg_penalty = pref_df["penalty_multiplier"].mean()
        max_penalty = pref_df["penalty_multiplier"].max()
        min_penalty = pref_df["penalty_multiplier"].min()

        logger.info(f"Penalty Statistics:")
        logger.info(f"  Average: {avg_penalty:.2f}x")
        logger.info(f"  Range: {min_penalty:.2f}x - {max_penalty:.2f}x")

        # High penalty listings (>2x cost increase)
        high_penalty_mask = pref_df["penalty_multiplier"] > 2.0
        if high_penalty_mask.any():
            high_penalty_count = high_penalty_mask.sum()
            logger.warning(f"⚠️  {high_penalty_count} listings with high penalties (>2x):")

            high_penalty_df = pref_df[high_penalty_mask].nlargest(10, "penalty_multiplier")
            for _, row in high_penalty_df.iterrows():
                logger.warning(f"  {row['name']} at {row['site_name']}: " f"{row['penalty_multiplier']:.1f}x penalty")
                logger.warning(f"    Reason: {row['penalty_explanation']}")

        # Strict filter rejections
        strict_rejections = pref_df[pref_df["penalty_explanation"] == "strict_filter"]
        if not strict_rejections.empty:
            logger.warning(f"❌ {len(strict_rejections)} listings rejected by strict preferences")

            # Group by card to show which cards are most affected
            rejection_by_card = strict_rejections.groupby("name").size().sort_values(ascending=False)
            for card_name, count in rejection_by_card.head(5).items():
                logger.warning(f"  {card_name}: {count} listings rejected")

        # Cards with no viable options after penalties
        expensive_cards = []
        for card_name in pref_df["name"].unique():
            card_listings = pref_df[pref_df["name"] == card_name]
            min_price = card_listings["weighted_price"].min()
            if min_price >= 10000:  # High cost threshold
                expensive_cards.append(card_name)

        if expensive_cards:
            logger.error(f"💰 Cards with no viable options after penalties: {expensive_cards}")

        logger.info("=" * 60)

    @staticmethod
    def _log_solution_penalty_summary(results):
        """Log summary of penalties in the final solution"""
        logger.info("=" * 60)
        logger.info("📊 FINAL SOLUTION PENALTY SUMMARY")
        logger.info("=" * 60)

        total_cards = len(results)
        penalized_cards = [r for r in results if r.get("penalty_multiplier", 1.0) > 1.0]

        if penalized_cards:
            logger.info(f"Cards with penalties: {len(penalized_cards)}/{total_cards}")

            # Calculate cost impact
            original_total = sum(r["original_price"] * r["quantity"] for r in results)
            weighted_total = sum(r["weighted_price"] * r["quantity"] for r in results)
            cost_increase = weighted_total - original_total

            logger.info(f"Original cost: ${original_total:.2f}")
            logger.info(f"Weighted cost: ${weighted_total:.2f}")
            logger.info(f"Penalty impact: +${cost_increase:.2f} ({(cost_increase/original_total)*100:.1f}%)")

            # Show most penalized cards in solution
            high_penalty_cards = sorted(penalized_cards, key=lambda x: x["penalty_multiplier"], reverse=True)[:5]
            logger.info("Most penalized cards in solution:")
            for card in high_penalty_cards:
                logger.info(f"  {card['name']}: {card['penalty_multiplier']:.1f}x - {card['penalty_explanation']}")
        else:
            logger.info("No penalties applied to cards in final solution")

        logger.info("=" * 60)

    @staticmethod
    def _run_feasibility_scan(
        unique_stores,
        total_required_cards,
        evaluate_solution_fn,
    ):
        complete_solutions = []
        best_store_count = None
        best_solution = None

        for store_count in range(1, len(unique_stores) + 1):
            logger.info("=" * 30)
            logger.info(f"[Feasibility] Trying solution with {store_count} store(s):")

            result = evaluate_solution_fn(store_count, zero_weights=True)
            if not result:
                continue

            if result.get("nbr_card_in_solution") == total_required_cards:
                complete_solutions.append(result)
                if best_store_count is None:
                    best_store_count = store_count
                if not best_solution or result["total_price"] < best_solution["total_price"]:
                    best_solution = result
                    logger.info(">>> New best complete solution found!")

                if len(complete_solutions) > 1:
                    prev = complete_solutions[-2]["total_price"]
                    curr = complete_solutions[-1]["total_price"]
                    if (prev - curr) < (curr * 0.1):
                        logger.info("Stopping search — minimal cost improvement")
                        break

        return complete_solutions, best_store_count, best_solution

    @staticmethod
    def _reoptimize_with_weights(
        best_store_count,
        evaluate_solution_fn,
        complete_solutions,
    ):
        logger.info(f"Re-optimizing with weights at best store count = {best_store_count}")
        weighted_result = evaluate_solution_fn(best_store_count, zero_weights=False)

        if weighted_result and weighted_result["nbr_card_in_solution"] == weighted_result["total_card_count"]:
            logger.info(">>> Weighted optimization succeeded after feasibility pass")
            best_solution = weighted_result
        else:
            best_price = min(sol["total_price"] for sol in complete_solutions)
            near_best = [sol for sol in complete_solutions if sol["total_price"] <= best_price * 1.05]
            best_solution = min(near_best, key=lambda x: x["number_store"]) if near_best else complete_solutions[0]

        return best_solution

    @staticmethod
    def _compute_pulp_optimization(
        filtered_listings_df,
        user_wishlist_df,
        unique_cards,
        unique_stores,
        raw_costs,
        enriched_costs,
        total_qty,
        optimizationConfig,
    ):
        """Run the MILP optimization with the setup data."""
        try:
            all_iterations_results = []
            best_solution = None

            logger.info("=" * 50)
            logger.info(f"Total cards to find: {total_qty}")
            logger.info(f"Available stores: {len(unique_stores)}")
            strategy_msg = (
                "Minimize store count"
                if optimizationConfig.find_min_store
                else f"Minimum {optimizationConfig.min_store} stores"
            )
            logger.info(f"Strategy: {strategy_msg}")

            # --- Shared evaluation helper ---
            def evaluate_solution(store_count, zero_weights=False):
                weights = (optimizationConfig.weights or {}).copy()
                if zero_weights:
                    weights = {k: 0.0 for k in weights}

                filtered = filtered_listings_df.copy()
                if zero_weights:
                    filtered["weighted_price"] = filtered["price"]

                costs_to_use = enriched_costs

                prob, buy_vars, total_possible_cost = PurchaseOptimizer._setup_prob(
                    costs_to_use,
                    unique_cards,
                    unique_stores,
                    user_wishlist_df,
                    optimizationConfig,
                    store_count,
                    weights=weights,
                )

                if pulp.LpStatus[prob.status] == "Infeasible":
                    logger.warning(f"[MILP Debug] Infeasible at {store_count} stores.")
                    for card in unique_cards:
                        available_stores = [
                            s for s in costs_to_use[card] if costs_to_use[card][s].get("weighted_price", 10000) < 10000
                        ]
                        if not available_stores:
                            logger.warning(f"  Card {card} has no valid listings at this store count.")

                if pulp.LpStatus[prob.status] != "Optimal":
                    logger.info(f"No feasible solution found with {store_count} store(s)")
                    return None

                result = PurchaseOptimizer._process_result(buy_vars, costs_to_use, filtered)
                result["total_card_count"] = total_qty

                normalized_cost = result.get("total_price", 0) / total_possible_cost
                normalized_store_count = result.get("number_store", 0) / len(unique_stores)
                normalized_quality = result.get("normalized_quality")
                if normalized_quality is None:
                    logger.warning("Missing normalized_quality in result; defaulting to 0.")
                    normalized_quality = 0

                weighted_score = (
                    weights.get("cost", 0.0) * normalized_cost
                    + weights.get("store_count", 0.0) * normalized_store_count
                    + weights.get("quality", 0.0) * normalized_quality
                )
                result["weighted_score"] = round(weighted_score, 6)
                logger.info(f"Weighted score: {result['weighted_score']}")

                if result["missing_cards_count"] > 0:
                    logger.warning(
                        f"[MILP][{store_count} stores] Infeasible due to missing cards: {result['missing_cards']}"
                    )
                else:
                    logger.info(
                        f"[MILP][{store_count} stores]  Found complete solution with {len(result['stores'])} stores, "
                        f"cost ${result['total_price']:.2f}"
                    )
                all_iterations_results.append(result)
                PurchaseOptimizer.print_detailed_solution_summary(
                    {"best_solution": result, "type": "iterations"}, total_qty
                )

                return result

            # --- Strategy 1: Minimize store count ---
            if optimizationConfig.find_min_store:
                logger.info("Starting optimization first pass to find_min_store ")
                evaluate = lambda store_count, zero_weights=False: evaluate_solution(
                    store_count, zero_weights=zero_weights
                )

                logger.info("Running feasibility scan... ")
                complete_solutions, best_store_count, _ = PurchaseOptimizer._run_feasibility_scan(
                    unique_stores, total_qty, evaluate
                )

                if not complete_solutions:
                    logger.warning("No complete solution found during store count minimization")
                    return None, all_iterations_results

                logger.info("Re-optimizing with weights... ")
                best_solution = PurchaseOptimizer._reoptimize_with_weights(
                    best_store_count, evaluate, complete_solutions
                )

                logger.info("Printing solutions... ")
                PurchaseOptimizer.print_detailed_solution_summary(best_solution, total_qty)
                return best_solution["sorted_results_df"], all_iterations_results
            # --- Strategy 2: Optimize with fixed min_store ---
            else:
                result = evaluate_solution(optimizationConfig.min_store)
                if result:
                    best_solution = result
                    logger.info(">>> Optimization with fixed min_store succeeded.")
                    PurchaseOptimizer.print_detailed_solution_summary(best_solution, total_qty)
                    return best_solution["sorted_results_df"], all_iterations_results

                logger.warning("No feasible solution with the minimum store constraint.")
                return None, all_iterations_results

        except Exception as e:
            logger.error(f"Error in compute_pulp_optimization: {str(e)}", exc_info=True)
            return None, None

    def run_milp_optimization(self):
        return self._run_pulp(
            self.filtered_listings_df,
            self.user_wishlist_df,
        )

    # Modified _run_pulp to use the split functions
    def _run_pulp(self, filtered_listings_df, user_wishlist_df):
        """Main MILP optimization function."""
        try:
            # Setup phase
            setup_results = self._setup_pulp_optimization(filtered_listings_df, user_wishlist_df)

            if any(result is None for result in setup_results):
                return None, None

            filtered_listings_df, unique_cards, unique_stores, raw_costs, enriched_costs, total_qty = setup_results

            # Validate minimum store requirement
            if len(unique_stores) < self.optimizationConfig.min_store:
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
                raw_costs,
                enriched_costs,  # instead of costs_to_use
                total_qty,
                self.optimizationConfig,
            )

        except Exception as e:
            logger.error("_run_pulp: %s", str(e))
            logger.error("DataFrame columns: %s", filtered_listings_df.columns.tolist())
            raise

    @staticmethod
    def _setup_prob(
        costs_enriched, unique_cards, unique_stores, user_wishlist, optimizationConfig, store_count=None, weights=None
    ):
        """Setup MILP problem with proper store constraints"""

        prob = pulp.LpProblem("MTGCardOptimization", pulp.LpMinimize)

        if weights is None:
            weights = optimizationConfig.weights or {}

        # Fallbacks
        cost_weight = weights.get("cost", 1.0)
        availability_weight = weights.get("availability", 1.0)
        quality_weight = weights.get("quality", 1.0)
        store_weight = weights.get("store_count", 1.0)

        logger.info(
            f"[MILP] Solving model with weights: cost={cost_weight}, store_count={store_weight}, "
            f"quality={quality_weight}, availability={availability_weight}"
        )

        def debug_solver():
            # DEBUG: Analyze feasibility before creating the problem
            logger.info("=== FEASIBILITY ANALYSIS ===")
            logger.info(f"Cards needed: {len(unique_cards)}")
            logger.info(f"Stores available: {len(unique_stores)}")
            logger.info(f"Target store count: {store_count}")

            # Check which cards are available in which stores
            cards_per_store = {}
            stores_per_card = {}

            for card in unique_cards:
                available_stores = list(costs_enriched.get(card, {}).keys())
                stores_per_card[card] = available_stores
                logger.info(f"Card '{card}': available in {len(available_stores)} stores")

                if len(available_stores) == 0:
                    logger.error(f"CRITICAL: Card '{card}' has NO available stores!")

                for store in available_stores:
                    if store not in cards_per_store:
                        cards_per_store[store] = []
                    cards_per_store[store].append(card)

            # Analyze store coverage
            logger.info("=== STORE COVERAGE ===")
            for store, cards in sorted(cards_per_store.items(), key=lambda x: len(x[1]), reverse=True):
                logger.info(f"Store '{store}': has {len(cards)}/{len(unique_cards)} cards")

            # Check if any single store has all cards
            max_coverage = max(len(cards) for cards in cards_per_store.values()) if cards_per_store else 0
            logger.info(f"Best single store coverage: {max_coverage}/{len(unique_cards)} cards")

            if store_count and store_count == 1 and max_coverage < len(unique_cards):
                logger.error(f"INFEASIBLE: No single store has all {len(unique_cards)} cards!")
                logger.error(
                    f"Best store only has {max_coverage} cards. Need at least {len(unique_cards) - max_coverage} more stores."
                )

            # Find minimum stores needed (greedy approximation)
            remaining_cards = set(unique_cards)
            stores_needed = []

            while remaining_cards and len(stores_needed) < 10:  # Limit to avoid infinite loop
                # Find store with most remaining cards
                best_store = None
                best_coverage = 0

                for store, cards in cards_per_store.items():
                    if store in stores_needed:
                        continue
                    coverage = len(set(cards) & remaining_cards)
                    if coverage > best_coverage:
                        best_coverage = coverage
                        best_store = store

                if best_store:
                    stores_needed.append(best_store)
                    remaining_cards -= set(cards_per_store[best_store])
                    logger.info(
                        f"Store {len(stores_needed)}: '{best_store}' covers {best_coverage} more cards, {len(remaining_cards)} remaining"
                    )
                else:
                    break

            logger.info(f"MINIMUM STORES NEEDED: {len(stores_needed)} stores for complete coverage")
            if remaining_cards:
                logger.error(
                    f"IMPOSSIBLE: {len(remaining_cards)} cards cannot be found in any store: {list(remaining_cards)}"
                )

            logger.info("=== END FEASIBILITY ANALYSIS ===")

        # debug_solver()
        # Continue with the rest of your _setup_prob method...
        buy_vars = {}
        for card in unique_cards:
            buy_vars[card] = {}
            for store in costs_enriched[card]:
                buy_vars[card][store] = pulp.LpVariable(f"Buy_{card}_{store}", 0, 1, pulp.LpBinary)
        store_vars = {}
        for store in unique_stores:
            store_vars[store] = pulp.LpVariable(f"Store_{store}", 0, 1, pulp.LpBinary)
        # Decision variables
        # buy_vars = pulp.LpVariable.dicts("Buy", (unique_cards, unique_stores), 0, 1, pulp.LpBinary)
        # store_vars = pulp.LpVariable.dicts("Store", unique_stores, 0, 1, pulp.LpBinary)

        objective_terms = []

        # Cost
        total_possible_cost = sum(
            min(costs_enriched[card][store]["weighted_price"] for store in costs_enriched[card])
            for card in unique_cards
            if costs_enriched[card]
        )

        if cost_weight > 0 and total_possible_cost > 0:
            normalized_cost_term = (
                pulp.lpSum(
                    buy_vars[card][store] * costs_enriched[card][store]["weighted_price"]
                    for card in unique_cards
                    for store in costs_enriched.get(card, {})  # FIXED: Use costs_enriched structure
                )
                / total_possible_cost
            )
            objective_terms.append(cost_weight * normalized_cost_term)

        # Store count
        if store_weight > 0:
            normalized_store_term = pulp.lpSum(store_vars[store] for store in unique_stores) / len(unique_stores)
            objective_terms.append(store_weight * normalized_store_term)

        quality_penalties = []

        total_quality_slots = 0
        max_weight = max(CardQuality.get_weight(q.value) for q in CardQuality)

        for card in unique_cards:
            for store in unique_stores:
                listing = costs_enriched.get(card, {}).get(store)
                if not listing:
                    continue

                quality_score = listing.get("quality_score")
                if quality_score is None:
                    normalized_quality = CardQuality.normalize(listing.get("quality", "DMG"))
                    quality_score = 1 - (CardQuality.get_weight(normalized_quality) - 1) / (max_weight - 1)
                q_penalty = 1 - quality_score
                quality_penalties.append(q_penalty * buy_vars[card][store])
                total_quality_slots += 1

        if quality_weight > 0 and total_quality_slots > 0:
            normalized_quality_term = 1 - (pulp.lpSum(quality_penalties) / total_quality_slots)
            objective_terms.append(quality_weight * normalized_quality_term)

        if objective_terms:
            prob += pulp.lpSum(objective_terms), "WeightedObjective"
        else:
            logger.info("[MILP] Feasibility-only mode activated. Objective is dummy.")
            prob += pulp.lpSum([]), "FeasibilityObjective"

        # Quantity constraints
        for card in unique_cards:
            required_quantity = user_wishlist[user_wishlist["name"] == card]["quantity"].iloc[0]
            available_stores = list(costs_enriched.get(card, {}).keys())

            if available_stores:
                prob += (
                    pulp.lpSum([buy_vars[card][store] for store in available_stores]) == required_quantity,
                    f"Required_quantity_{card}",
                )
            else:
                logger.warning(
                    f"Card {card} is not available at any of the considered stores (required qty: {required_quantity})."
                )

        # Store activation linkage
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
            else:
                # If no card can be bought from this store, deactivate it
                prob += store_vars[store] == 0, f"Store_unused_{store}"

        # Store constraints
        min_store = optimizationConfig.min_store
        max_store = optimizationConfig.max_store
        if len(unique_stores) < min_store:
            logger.warning(f"Adjusting min_store from {min_store} to {len(unique_stores)} due to available stores")
            min_store = len(unique_stores)

        used_store_vars = [store_vars[store] for store in unique_stores if store in store_vars]
        if optimizationConfig.find_min_store is True:
            if used_store_vars:
                prob += (pulp.lpSum(used_store_vars) >= min_store, "Min_stores")
                if store_count:
                    prob += (pulp.lpSum(used_store_vars) <= store_count, "Max_store_cap_for_find_min")
        else:
            # STRATEGY 2: Standard optimization with min/max store bounds
            if used_store_vars:
                # Enforce minimum stores constraint
                prob += (pulp.lpSum(used_store_vars) >= min_store, "Min_stores_required")
                # Enforce maximum stores constraint
                prob += (pulp.lpSum(used_store_vars) <= max_store, "Max_stores_allowed")

                logger.info(f"Added store constraints: {min_store} <= stores <= {max_store}")

        # For debugging - get detailed solver output
        def get_debug_solver():
            return PULP_CBC_CMD(
                msg=True,  # Show solver messages
                threads=4,  # Use multiple threads
                timeLimit=120,  # Increase time limit
                gapRel=0.01,  # Stop at 1% optimality gap
                presolve=True,  # Enable presolving
                cuts=True,  # Enable cutting planes
                strong=5,  # Strong branching depth
                options=[
                    "preprocess on",  # Enable preprocessing
                    "cuts on",  # Enable all cuts
                    "heuristics on",  # Enable heuristics
                    "printingOptions all",  # Detailed output
                    "logLevel 2",  # Verbose logging
                ],
            )

        # For production - fast and quiet
        def get_production_solver():
            return PULP_CBC_CMD(
                msg=False,  # Quiet
                threads=4,  # Use multiple threads
                timeLimit=60,  # Standard time limit
                gapRel=0.05,  # Stop at 5% optimality gap (faster)
                presolve=True,  # Enable presolving
                cuts=True,  # Enable cutting planes
                strong=10,  # Deeper strong branching
                options=["preprocess on", "cuts on", "heuristics on"],
            )

        # For infeasible problems - get detailed infeasibility analysis
        def get_infeasibility_solver():
            return PULP_CBC_CMD(
                msg=True,
                threads=1,  # Single thread for clearer output
                timeLimit=30,  # Short time limit
                options=[
                    "preprocess off",  # Disable preprocessing to see raw problem
                    "printingOptions all",  # Maximum detail
                    "logLevel 3",  # Maximum logging
                    "feasibilityPump on",  # Try feasibility pump heuristic
                    "solve",
                ],
            )

        # DEBUG: Analyze the constraints that were created
        logger.info("=== CONSTRAINT DEBUGGING ===")
        logger.info(f"Total constraints created: {len(prob.constraints)}")

        # Debug quantity constraints
        quantity_constraints = [name for name in prob.constraints.keys() if name.startswith("Required_quantity_")]
        # logger.info(f"Quantity constraints: {len(quantity_constraints)}")
        # for constraint_name in quantity_constraints[:5]:  # Show first 5
        #     constraint = prob.constraints[constraint_name]
        #     logger.info(f"  {constraint_name}: {constraint}")

        # Debug store constraints
        # store_constraints = [name for name in prob.constraints.keys() if "store" in name.lower()]
        # logger.info(f"Store-related constraints: {len(store_constraints)}")
        # for constraint_name in store_constraints:
        #     constraint = prob.constraints[constraint_name]
        #     logger.info(f"  {constraint_name}: {constraint}")

        # Debug variables
        logger.info(f"Total variables: {len(prob.variables())}")
        buy_var_count = len([v for v in prob.variables() if v.name.startswith("Buy_")])
        store_var_count = len([v for v in prob.variables() if v.name.startswith("Store_")])
        logger.info(f"Buy variables: {buy_var_count}")
        logger.info(f"Store variables: {store_var_count}")

        # Debug the specific stores we know should work
        test_stores = ["facetofacegames", "gamekeeperonline", "mtgjeuxjubes"]
        logger.info("=== TESTING KNOWN GOOD STORES ===")
        for store in test_stores:
            if store in store_vars:
                logger.info(f"Store '{store}' variable exists: {store_vars[store].name}")
                # Check which cards can be bought from this store
                available_cards = [card for card in unique_cards if store in costs_enriched.get(card, {})]
                logger.info(f"  Can buy {len(available_cards)} cards from {store}")
                logger.info(f"  Cards: {available_cards[:10]}...")  # Show first 10
            else:
                logger.error(f"Store '{store}' variable MISSING!")

        # Test if the 3-store solution should work mathematically
        logger.info("=== MATHEMATICAL FEASIBILITY TEST ===")
        test_stores = ["facetofacegames", "gamekeeperonline", "mtgjeuxjubes"]
        covered_cards = set()
        for store in test_stores:
            available_cards = [card for card in unique_cards if store in costs_enriched.get(card, {})]
            covered_cards.update(available_cards)
            logger.info(f"After adding {store}: {len(covered_cards)}/{len(unique_cards)} cards covered")

        missing_cards = set(unique_cards) - covered_cards
        if missing_cards:
            logger.error(f"Cards still missing after 3 stores: {list(missing_cards)}")
        else:
            logger.info("✅ Mathematical verification: All cards can be covered with 3 stores!")

        logger.info("=== END CONSTRAINT DEBUGGING ===")
        # Solve
        if pulp.LpStatus[prob.status] == "Infeasible":
            # If we detect infeasibility, use specialized solver
            solver = get_infeasibility_solver()
        else:
            # For normal operation, use debug solver first
            # solver = get_debug_solver()
            solver = get_production_solver()

        prob.solve(solver)
        logger.info(f"Solver status: {pulp.LpStatus[prob.status]}")
        logger.info(f"Objective value: {pulp.value(prob.objective) if prob.objective else 'N/A'}")
        logger.info(f"Variables: {len(prob.variables())}")
        logger.info(f"Constraints: {len(prob.constraints)}")

        if pulp.LpStatus[prob.status] == "Optimal":
            logger.info("Feasible solution found.")
        else:
            logger.warning("No feasible solution found.")

        return prob, buy_vars, total_possible_cost

    @staticmethod
    def _process_result(buy_vars, costs, filtered_listings_df) -> Dict:
        total_price = 0.0
        results = []
        total_card_nbr = 0

        found_cards = set()
        all_cards = set(card for card, _ in buy_vars.items())
        store_usage = defaultdict(int)

        for card, store_dict in buy_vars.items():
            for store, var in store_dict.items():
                quantity = int(var.value() or 0)
                if quantity > 0:
                    try:
                        weighted_price = round(costs[card][store]["weighted_price"], 2)
                    except KeyError:
                        logger.error(f"[ERROR] No cost info for {card} at {store}")
                        continue
                    if weighted_price != 10000:  # Only include cards in solution
                        # Find matching cards using weighted_price instead of price
                        matching_cards = filtered_listings_df[
                            (filtered_listings_df["name"] == card)
                            & (filtered_listings_df["site_name"] == store)
                            & (abs(filtered_listings_df["weighted_price"] - weighted_price) < 0.01)
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
                        total_price += card_store_total_price
                        total_card_nbr += quantity
                        store_usage[store] += 1

                        if "variant_id" not in card_data or card_data.get("variant_id") is None:
                            logger.warning(f"Card missing variant_id during optimization: {card} at {store}")
                        if store not in costs.get(card, {}):
                            logger.warning(f"Skipping {card} at {store}, not present in cost matrix.")
                            continue

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

        for result in results:
            try:
                card_name = result["name"]
                site_name = result["site_name"]

                # Find the corresponding row in filtered_listings_df
                matching_row = filtered_listings_df[
                    (filtered_listings_df["name"] == card_name) & (filtered_listings_df["site_name"] == site_name)
                ]

                if not matching_row.empty:
                    row = matching_row.iloc[0]
                    result["penalty_multiplier"] = float(row.get("penalty_multiplier", 1.0))
                    result["penalty_explanation"] = str(row.get("penalty_explanation", ""))
                    result["preference_applied"] = bool(row.get("preference_applied", False))
                    result["original_price"] = result["price"]
                    result["weighted_price"] = float(row.get("weighted_price", result["price"]))
                else:
                    # Fallback values if matching row not found
                    result["penalty_multiplier"] = 1.0
                    result["penalty_explanation"] = "No penalty data available"
                    result["preference_applied"] = False
                    result["original_price"] = result["price"]
                    result["weighted_price"] = result["price"]
            except Exception as e:
                logger.warning(f"Failed to add penalty info for {result.get('name', 'unknown')}: {e}")
                # Set safe defaults
                result["penalty_multiplier"] = 1.0
                result["penalty_explanation"] = "Error retrieving penalty data"
                result["preference_applied"] = False
                result["original_price"] = result["price"]
                result["weighted_price"] = result["price"]

        # Log final solution penalty summary (with error handling)
        try:
            if results:
                PurchaseOptimizer._log_solution_penalty_summary(results)
        except Exception as e:
            logger.warning(f"Failed to log penalty summary: {e}")

        return {
            "nbr_card_in_solution": int(total_card_nbr),
            "total_price": float(total_price),
            "number_store": len(stores),
            "list_stores": store_usage_str,
            "stores": stores,
            "sorted_results_df": sorted_results_df,  # Keep as DataFrame
            "missing_cards": missing_cards,
            "missing_cards_count": len(missing_cards),
            "total_qty": real_total_qty,
        }

    def run_nsga_ii_optimization(self, milp_solution=None):
        return self._run_nsga_ii(
            self.filtered_listings_df, self.user_wishlist_df, self.optimizationConfig, milp_solution
        )

    def _run_nsga_ii(self, filtered_listings_df, user_wishlist_df, optimizationConfig, milp_solution=None):
        """Enhanced NSGA-II implementation with better solution tracking"""

        # Initialize parameters
        NGEN = 50
        POP_SIZE = 300
        TOURNAMENT_SIZE = 3
        CXPB = 0.85
        MUTPB = 0.15
        ELITE_SIZE = 30

        toolbox = self._initialize_toolbox(filtered_listings_df, user_wishlist_df, optimizationConfig)

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

    def _initialize_toolbox(self, filtered_listings_df, user_wishlist_df, optimizationConfig):
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
            self._evaluate_solution_wrapper(filtered_listings_df, user_wishlist_df, optimizationConfig),
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
                        CardQuality.get_weight(CardQuality.normalize(r["quality"])) / (float(r["price"]) + 0.1)
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
                        CardQuality.get_weight(CardQuality.normalize(r["quality"])) / (float(r["price"]) + 0.1)
                        for _, r in available_options.iterrows()
                    ]
                    individual[i] = random.choices(available_options.index, weights=weights, k=1)[0]
        return (individual,)

    def _evaluate_solution_wrapper(self, filtered_listings_df, user_wishlist_df, optimizationConfig):
        """Revised evaluation function with better handling of incomplete solutions."""

        def evaluate_solution(individual):
            stores_used = set()
            total_cost = 0
            quality_scores = []

            required_cards = {row["name"]: row["quantity"] for _, row in user_wishlist_df.iterrows()}
            found_cards = defaultdict(int)

            for idx in individual:
                if idx not in filtered_listings_df.index:
                    continue

                card = filtered_listings_df.loc[idx]
                card_name = card["name"]

                if found_cards[card_name] >= required_cards.get(card_name, 0):
                    continue

                prefs = self.card_preferences.get(card_name, {})
                weighted_price, penalty_multiplier, reason = PurchaseOptimizer._compute_penalized_price(
                    card,
                    prefs,
                    optimizationConfig.strict_preferences,
                    high_cost=10000,
                )

                if reason == "strict_filter":
                    continue  # Skip listing due to strict preference mismatch

                total_cost += weighted_price
                found_cards[card_name] += 1
                stores_used.add(card["site_name"])

                # Compute quality score
                normalized_quality = CardQuality.normalize(card.get("quality", "DMG"))
                max_weight = max(CardQuality.get_weight(q.value) for q in CardQuality)
                quality_score = 1 - (CardQuality.get_weight(normalized_quality) - 1) / (max_weight - 1)

                language = CardLanguage.normalize(card.get("language", "Unknown"))
                quality_score /= CardLanguage.get_weight(language)  # Penalize based on language weight

                quality_scores.append(quality_score)

            # Calculate core metrics
            total_cards_needed = sum(required_cards.values())
            total_cards_found = sum(found_cards.values())
            completeness = total_cards_found / total_cards_needed if total_cards_needed > 0 else 0
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            store_count = len(stores_used)

            # Store penalty
            store_penalty = (
                (store_count - optimizationConfig.max_unique_store) * 1000
                if store_count > optimizationConfig.max_unique_store
                else 0
            )

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
        # Use constant from app.constants
        quality_scores = []
        max_weight = max(CardQuality.get_weight(q.value) for q in CardQuality)

        for card in solution_data:
            normalized_quality = CardQuality.normalize(card.get("quality", "DMG"))
            score = 1 - (CardQuality.get_weight(normalized_quality) - 1) / (max_weight - 1)
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
