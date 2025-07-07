# backend/app/optimization/postprocessing/result_formatter.py
import logging
from typing import Dict, Any, List, Tuple, Optional, Union
import pandas as pd
import numpy as np
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SolutionType(Enum):
    """Enumeration of solution data types for proper dispatch"""

    MILP_SOLUTION_LIST = "milp_solution_list"
    EVOLUTIONARY_INDIVIDUAL = "evolutionary_individual"
    DATAFRAME = "dataframe"
    SOLUTION_DICT = "solution_dict"
    UNKNOWN = "unknown"


@dataclass
class SolutionData:
    """Structured container for solution data"""

    total_price: float
    cards_required_total: int
    unique_cards_found: int
    stores: List[Dict[str, Any]]
    missing_cards: List[str]
    store_usage_summary: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to the expected dictionary format"""
        return {
            "total_price": float(self.total_price),
            "nbr_card_in_solution": int(self.unique_cards_found),
            "cards_required_total": int(self.cards_required_total),
            "number_store": len(self.stores),
            "stores": self.stores,
            "list_stores": self.store_usage_summary,
            "missing_cards": self.missing_cards,
            "missing_cards_count": len(self.missing_cards),
        }


class ResultFormatter:
    """
    Efficiently format optimization results into standardized format.

    This class provides a unified interface for formatting results from different
    optimization algorithms with proper input validation and error handling.
    """

    def __init__(self):
        """Initialize result formatter."""
        self.filtered_listings_df: Optional[pd.DataFrame] = None

    def set_filtered_listings_df(self, df: pd.DataFrame) -> None:
        """
        Set the filtered listings DataFrame for reference.

        Args:
            df: DataFrame with filtered card listings
        """
        if df is not None and not df.empty:
            self.filtered_listings_df = df.copy()
        else:
            logger.warning("Attempted to set empty or None filtered_listings_df.")

    def format_solution(
        self,
        solution_data: Any,
        user_wishlist_df: pd.DataFrame,
        listings_df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Unified method to format any type of solution data into standardized format.

        Args:
            solution_data: Solution data from optimization algorithm
            user_wishlist_df: DataFrame with user wishlist
            listings_df: Optional DataFrame with listings (uses instance if not provided)
            algorithm_type: Type of algorithm for context (not used for dispatch)

        Returns:
            Standardized solution dictionary

        Raises:
            ValueError: If input data is invalid
            IndexError: If individual indices are out of bounds
        """
        # Input validation
        if user_wishlist_df is None or user_wishlist_df.empty:
            raise ValueError("user_wishlist_df cannot be None or empty")

        if solution_data is None:
            return self._create_empty_solution()

        # Use provided listings_df or fall back to instance variable
        working_listings_df = listings_df if listings_df is not None else self.filtered_listings_df
        if working_listings_df is None or working_listings_df.empty:
            raise ValueError("No valid listings DataFrame available")

        try:
            # Determine solution type and dispatch to appropriate handler
            solution_type = self._determine_solution_type(solution_data)

            if solution_type == SolutionType.MILP_SOLUTION_LIST:
                return self._format_milp_solution(solution_data, user_wishlist_df)

            elif solution_type == SolutionType.EVOLUTIONARY_INDIVIDUAL:
                return self._format_evolutionary_solution(solution_data, working_listings_df, user_wishlist_df)

            elif solution_type == SolutionType.DATAFRAME:
                return self._format_dataframe_solution(solution_data, user_wishlist_df)

            elif solution_type == SolutionType.SOLUTION_DICT:
                return self._validate_and_enhance_solution_dict(solution_data, user_wishlist_df)

            else:
                logger.warning(f"Unknown solution type for data: {type(solution_data)}")
                return self._create_empty_solution()

        except Exception as e:
            logger.error(f"Error formatting solution: {str(e)}")
            return self._create_empty_solution()

    def format_multiple_solutions(
        self,
        solutions: List[Any],
        user_wishlist_df: pd.DataFrame,
        listings_df: Optional[pd.DataFrame] = None,
        max_solutions: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Format multiple solutions efficiently.

        Args:
            solutions: List of solution data from optimization
            user_wishlist_df: DataFrame with user wishlist
            listings_df: Optional DataFrame with listings
            max_solutions: Maximum number of solutions to process

        Returns:
            List of standardized solution dictionaries
        """
        if not solutions:
            return []

        formatted_solutions = []
        processed_count = 0

        for solution in solutions:
            if processed_count >= max_solutions:
                break

            try:
                formatted = self.format_solution(solution, user_wishlist_df, listings_df)
                if formatted and formatted.get("total_price", 0) > 0:
                    formatted_solutions.append(formatted)
                    processed_count += 1
            except Exception as e:
                logger.warning(f"Failed to format solution {processed_count}: {str(e)}")
                continue

        logger.info(f"Successfully formatted {len(formatted_solutions)} out of {len(solutions)} solutions")
        return formatted_solutions

    def _determine_solution_type(self, solution_data: Any) -> SolutionType:
        """Determine the type of solution data for proper dispatch."""
        if isinstance(solution_data, dict):
            # Check if it's already a formatted solution dict
            if all(key in solution_data for key in ["total_price", "stores"]):
                return SolutionType.SOLUTION_DICT
            else:
                return SolutionType.UNKNOWN

        elif isinstance(solution_data, pd.DataFrame):
            return SolutionType.DATAFRAME

        elif isinstance(solution_data, (list, tuple, np.ndarray)):
            if len(solution_data) == 0:
                return SolutionType.UNKNOWN

            # Check if it's a list of card dictionaries (MILP format)
            if isinstance(solution_data[0], dict) and "name" in solution_data[0]:
                return SolutionType.MILP_SOLUTION_LIST

            # Check if it's a list of indices (evolutionary format)
            elif isinstance(solution_data[0], (int, np.integer)):
                return SolutionType.EVOLUTIONARY_INDIVIDUAL

            else:
                return SolutionType.UNKNOWN

        else:
            return SolutionType.UNKNOWN

    def _format_milp_solution(
        self, solution_list: List[Dict[str, Any]], user_wishlist_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Format MILP solution (list of card dictionaries)."""
        if not solution_list:
            return self._create_empty_solution()

        # Validate card dictionaries
        validated_cards = []
        for card in solution_list:
            if not isinstance(card, dict):
                logger.warning(f"Invalid card data type: {type(card)}")
                continue

            if "name" not in card or "price" not in card:
                logger.warning(f"Card missing required fields: {card}")
                continue

            validated_cards.append(card)

        if not validated_cards:
            return self._create_empty_solution()

        return self._create_solution_from_cards(validated_cards, user_wishlist_df)

    def _format_dataframe_solution(self, df: pd.DataFrame, user_wishlist_df: pd.DataFrame) -> Dict[str, Any]:
        """Format solution from DataFrame."""
        if df.empty:
            return self._create_empty_solution()

        try:
            cards = df.to_dict("records")
            return self._create_solution_from_cards(cards, user_wishlist_df)
        except Exception as e:
            logger.error(f"Error converting DataFrame to solution: {str(e)}")
            return self._create_empty_solution()

    def _format_evolutionary_solution(
        self, individual: List[int], listings_df: pd.DataFrame, user_wishlist_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Format evolutionary algorithm solution with clear card quantity tracking."""
        if not individual:
            return self._create_empty_solution()

        # CLEAR INITIALIZATION: Get required card quantities from wishlist
        cards_required_total = int(user_wishlist_df["quantity"].sum())
        cards_required_by_name = {row["name"]: int(row["quantity"]) for _, row in user_wishlist_df.iterrows()}

        # Validate indices are within bounds
        max_index = len(listings_df) - 1
        valid_indices = []

        for idx in individual:
            if not isinstance(idx, (int, np.integer)):
                logger.warning(f"Invalid index type: {type(idx)}")
                continue

            if idx < 0 or idx > max_index:
                logger.warning(f"Index {idx} out of bounds [0, {max_index}]")
                continue

            valid_indices.append(int(idx))

        if not valid_indices:
            logger.warning("No valid indices found in individual")
            return self._create_empty_solution()

        # Convert indices to card purchases with quantity tracking
        cards = []
        cards_found_by_name = defaultdict(int)  # Track how many of each card we've found

        for idx in valid_indices:
            try:
                card_data = listings_df.iloc[idx].to_dict()
                card_name = card_data["name"]

                # Check if we need more of this card based on wishlist
                required_qty = cards_required_by_name.get(card_name, 0)
                found_qty = cards_found_by_name[card_name]

                if found_qty < required_qty:
                    card_data["quantity"] = 1
                    cards.append(card_data)
                    cards_found_by_name[card_name] += 1
                # If we already have enough of this card, skip it

            except Exception as e:
                logger.warning(f"Error processing index {idx}: {str(e)}")
                continue

        # CLEAR LOGGING: Report what we found vs what we needed
        cards_found_total = sum(cards_found_by_name.values())
        cards_found_unique = len(cards_found_by_name)

        logger.debug(f"Evolutionary solution conversion:")
        logger.debug(f"  Required: {cards_required_total} cards ({len(cards_required_by_name)} unique)")
        logger.debug(f"  Found: {cards_found_total} cards ({cards_found_unique} unique)")

        return self._create_solution_from_cards(cards, user_wishlist_df)

    def _validate_and_enhance_solution_dict(
        self, solution_dict: Dict[str, Any], user_wishlist_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Validate and enhance an existing solution dictionary."""
        try:
            # Ensure all required fields are present
            required_fields = ["total_price", "stores", "number_store"]
            enhanced = solution_dict.copy()

            for field in required_fields:
                if field not in enhanced:
                    logger.warning(f"Missing required field {field} in solution dict")
                    if field == "total_price":
                        enhanced[field] = 0.0
                    elif field == "stores":
                        enhanced[field] = []
                    elif field == "number_store":
                        enhanced[field] = 0

            # Recalculate missing cards if not present
            if "missing_cards" not in enhanced:
                enhanced.update(self._calculate_missing_cards(enhanced.get("stores", []), user_wishlist_df))

            return enhanced

        except Exception as e:
            logger.error(f"Error validating solution dict: {str(e)}")
            return solution_dict

    def _create_solution_from_cards(
        self, cards: List[Dict[str, Any]], user_wishlist_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Create standardized solution from list of card purchases with clear variable names."""
        if not cards:
            return self._create_empty_solution()

        try:
            # CLEAR CALCULATION: Get required cards from wishlist (not from solution)
            cards_required_total = int(user_wishlist_df["quantity"].sum())
            cards_required_unique = len(user_wishlist_df)

            # CLEAR CALCULATION: Count what we actually found in the solution
            cards_found_total = sum(int(card.get("quantity", 1)) for card in cards)
            cards_found_unique_names = set(card["name"] for card in cards)
            cards_found_unique = len(cards_found_unique_names)

            # Calculate financial metrics
            total_price = sum(float(card.get("price", 0)) * int(card.get("quantity", 1)) for card in cards)

            # Calculate completeness metrics
            completeness_by_quantity = cards_found_total / cards_required_total if cards_required_total > 0 else 0.0
            completeness_by_unique = cards_found_unique / cards_required_unique if cards_required_unique > 0 else 0.0

            # Group cards by store
            stores_data = defaultdict(list)
            for card in cards:
                site_name = card.get("site_name", "Unknown Store")
                stores_data[site_name].append(card)

            # Create store structures
            stores = []
            for site_name, store_cards in stores_data.items():
                site_id = store_cards[0].get("site_id") if store_cards else None
                stores.append({"site_name": site_name, "site_id": site_id, "cards": store_cards})

            # Calculate missing cards
            missing_info = self._calculate_missing_cards(stores, user_wishlist_df)

            # Create store usage summary
            store_usage_summary = ", ".join(f"{store['site_name']}: {len(store['cards'])}" for store in stores)

            result = {
                # Card quantity metrics (clear naming)
                "cards_required_total": cards_required_total,
                "cards_required_unique": cards_required_unique,
                "cards_found_total": cards_found_total,
                "cards_found_unique": cards_found_unique,
                # Completeness metrics
                "completeness_by_quantity": completeness_by_quantity,
                "completeness_by_unique": completeness_by_unique,
                "is_complete": completeness_by_quantity >= 1.0,
                # Missing cards
                "missing_cards": missing_info["missing_cards"],
                "missing_cards_count": missing_info["missing_cards_count"],
                # Financial and store metrics
                "total_price": float(total_price),
                "number_store": len(stores),
                "list_stores": store_usage_summary,
                "stores": stores,
                # Legacy compatibility (deprecated but kept for backward compatibility)
                "nbr_card_in_solution": cards_found_total,
                "total_card_found": cards_found_total,  # Remove these eventually
            }

            return result

        except Exception as e:
            logger.error(f"Error creating solution from cards: {str(e)}")
            return self._create_empty_solution()

    def _calculate_missing_cards(self, stores: List[Dict[str, Any]], user_wishlist_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate which cards are missing from the solution."""
        try:
            # Get all cards in solution
            unique_cards_found = set()
            for store in stores:
                for card in store.get("cards", []):
                    unique_cards_found.add(card["name"])

            # Get required cards from wishlist
            required_cards = set(user_wishlist_df["name"])

            # Calculate missing cards
            missing_cards = list(required_cards - unique_cards_found)

            return {"missing_cards": missing_cards, "missing_cards_count": len(missing_cards)}

        except Exception as e:
            logger.error(f"Error calculating missing cards: {str(e)}")
            return {"missing_cards": [], "missing_cards_count": 0}

    def _create_empty_solution(self) -> Dict[str, Any]:
        """Create an empty solution structure with consistent field names."""
        return {
            # Card quantity metrics
            "cards_required_total": 0,
            "cards_required_unique": 0,
            "cards_found_total": 0,
            "cards_found_unique": 0,
            # Completeness metrics
            "completeness_by_quantity": 0.0,
            "completeness_by_unique": 0.0,
            "is_complete": False,
            # Missing cards
            "missing_cards": [],
            "missing_cards_count": 0,
            # Financial and store metrics
            "total_price": 0.0,
            "number_store": 0,
            "list_stores": "",
            "stores": [],
            # Legacy compatibility (deprecated)
            "nbr_card_in_solution": 0,
            "total_card_found": 0,
        }

    def add_penalty_info_to_results(
        self, results: List[Dict[str, Any]], listings_df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        Add penalty information to results (legacy compatibility).

        Args:
            results: List of card results
            listings_df: DataFrame with listings including penalty info

        Returns:
            Enhanced results with penalty information
        """
        if not results or listings_df is None or listings_df.empty:
            return results

        try:
            enhanced_results = []
            penalty_columns = ["penalty_multiplier", "penalty_explanation", "weighted_price"]

            for result in results:
                enhanced_result = result.copy()

                # Try to find matching row in listings_df to get penalty info
                try:
                    matching_rows = listings_df[
                        (listings_df["name"] == result.get("name", ""))
                        & (listings_df["site_name"] == result.get("site_name", ""))
                    ]

                    if not matching_rows.empty:
                        penalty_info = matching_rows.iloc[0]
                        for col in penalty_columns:
                            if col in penalty_info:
                                enhanced_result[f"penalty_{col}"] = penalty_info[col]

                except Exception as e:
                    logger.warning(f"Failed to add penalty info for {result.get('name', 'unknown')}: {e}")

                enhanced_results.append(enhanced_result)

            return enhanced_results

        except Exception as e:
            logger.error(f"Error adding penalty info to results: {str(e)}")
            return results
