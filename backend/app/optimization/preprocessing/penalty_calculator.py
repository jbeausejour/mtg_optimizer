# backend/app/optimization/preprocessing/penalty_calculator.py
import logging
from typing import Dict, Tuple, Any, Optional, Union
import pandas as pd
import numpy as np
from dataclasses import dataclass
from app.constants import CardQuality, CardLanguage, CardVersion

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PenaltyConfig:
    """Immutable configuration for penalty calculations"""

    strict_preferences: bool = False
    high_cost: float = 10000.0
    weights: Dict[str, float] = None

    def __post_init__(self):
        if self.weights is None:
            object.__setattr__(self, "weights", {})


class PenaltyCalculator:
    """
    Efficiently calculate penalties for cards based on user preferences.

    This class provides true vectorized operations using pandas for optimal performance.
    All methods are thread-safe and use immutable configurations.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize penalty calculator with configuration.

        Args:
            config: Configuration dictionary with penalty settings
        """
        # Create immutable config
        self.config = PenaltyConfig(
            strict_preferences=config.get("strict_preferences", False),
            high_cost=config.get("high_cost", 10000.0),
            weights=config.get("weights", {}),
        )

        # Pre-compute penalty lookup tables for performance
        self._quality_weights = self._build_quality_lookup()
        self._language_weights = self._build_language_lookup()

        logger.debug(f"PenaltyCalculator initialized with strict_preferences={self.config.strict_preferences}")

    def apply_penalties(
        self,
        df: pd.DataFrame,
        card_preferences: Optional[Dict[str, Dict[str, Any]]] = None,
        config_override: Optional[PenaltyConfig] = None,
    ) -> pd.DataFrame:
        """
        Apply penalties to card listings using true vectorized operations.

        Args:
            df: DataFrame with card listings
            card_preferences: Dict mapping card names to preference dicts
            config_override: Optional config override for this operation

        Returns:
            DataFrame with added penalty columns:
            - weighted_price: Price after applying all penalties
            - penalty_multiplier: Total penalty multiplier applied
            - penalty_explanation: Human-readable explanation of penalties

        Raises:
            ValueError: If DataFrame is invalid or missing required columns
        """
        # Input validation
        if df is None or df.empty:
            raise ValueError("DataFrame cannot be None or empty")

        required_cols = ["name", "price", "site_name"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"DataFrame missing required columns: {missing_cols}")

        # Use provided config or default
        config = config_override or self.config
        preferences = card_preferences or {}

        # Work on copy to avoid modifying original
        result_df = df.copy()

        # Initialize penalty columns
        result_df["penalty_multiplier"] = 1.0
        result_df["penalty_explanation"] = "No penalties applied"
        result_df["preference_applied"] = False

        try:
            # Step 1: Apply base quality penalties (vectorized)
            result_df = self._apply_quality_penalties_vectorized(result_df)

            # Step 2: Apply user preference penalties (vectorized where possible)
            if preferences:
                result_df = self._apply_preference_penalties_vectorized(result_df, preferences, config)

            # Step 3: Calculate final weighted prices
            result_df["weighted_price"] = result_df["price"] * result_df["penalty_multiplier"]

            # Log performance statistics
            self._log_penalty_statistics(result_df, bool(preferences))

            return result_df

        except Exception as e:
            logger.error(f"Error applying penalties: {str(e)}")
            # Return DataFrame with basic weighted prices as fallback
            result_df["weighted_price"] = result_df["price"]
            return result_df

    def compute_single_penalty(
        self,
        card_data: Union[pd.Series, Dict[str, Any]],
        preferences: Dict[str, Any],
        config: Optional[PenaltyConfig] = None,
    ) -> Tuple[float, float, str]:
        """
        Compute penalty for a single card (pure function, thread-safe).

        Args:
            card_data: Card data as Series or dict
            preferences: User preferences for this card
            config: Optional config override

        Returns:
            Tuple of (final_price, penalty_multiplier, explanation)
        """
        config = config or self.config

        if isinstance(card_data, pd.Series):
            card_dict = card_data.to_dict()
        else:
            card_dict = card_data.copy()

        base_price = float(card_dict.get("price", config.high_cost))

        # Apply quality penalty
        quality = card_dict.get("quality", "DMG")
        quality_multiplier = self._quality_weights.get(quality, 1.5)

        # Apply preference penalties
        preference_multiplier, explanations = self._calculate_preference_penalties(card_dict, preferences, config)

        # Handle strict preferences
        if config.strict_preferences and preference_multiplier > 1.0:
            return config.high_cost, config.high_cost / base_price, "strict_filter"

        total_multiplier = quality_multiplier * preference_multiplier
        final_price = base_price * total_multiplier

        explanation = "; ".join(explanations) if explanations else "No preference penalties"

        return final_price, total_multiplier, explanation

    def _apply_quality_penalties_vectorized(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply quality penalties using vectorized operations."""
        # Map quality values to penalty multipliers
        quality_series = df["quality"].fillna("DMG")
        quality_multipliers = quality_series.map(self._quality_weights).fillna(1.5)

        # Update penalty multiplier
        df["penalty_multiplier"] *= quality_multipliers

        # Add explanations for quality penalties
        quality_mask = quality_multipliers > 1.0
        if quality_mask.any():
            df.loc[quality_mask, "penalty_explanation"] = (
                "Quality: " + quality_series + " (penalty: " + quality_multipliers.round(1).astype(str) + "x)"
            )

        return df

    def _apply_preference_penalties_vectorized(
        self, df: pd.DataFrame, preferences: Dict[str, Dict[str, Any]], config: PenaltyConfig
    ) -> pd.DataFrame:
        """Apply user preference penalties using vectorized operations where possible."""

        # Get cards with preferences
        cards_with_prefs = set(preferences.keys())
        pref_mask = df["name"].isin(cards_with_prefs)

        if not pref_mask.any():
            return df

        # Process cards with preferences
        pref_df = df[pref_mask].copy()

        # Vectorized preference processing by attribute
        for attr in ["language", "version", "quality", "foil", "set_name"]:
            pref_df = self._apply_attribute_penalties_vectorized(pref_df, preferences, attr, config)

        # Update original DataFrame
        df.loc[pref_mask, "penalty_multiplier"] = pref_df["penalty_multiplier"]
        df.loc[pref_mask, "penalty_explanation"] = pref_df["penalty_explanation"]
        df.loc[pref_mask, "preference_applied"] = True

        return df

    def _apply_attribute_penalties_vectorized(
        self, df: pd.DataFrame, preferences: Dict[str, Dict[str, Any]], attribute: str, config: PenaltyConfig
    ) -> pd.DataFrame:
        """Apply penalties for a specific attribute using vectorization."""

        # Create preference lookup for this attribute
        attr_prefs = {}
        for card_name, card_prefs in preferences.items():
            expected_value = card_prefs.get(attribute)
            if expected_value is not None and expected_value != "":
                attr_prefs[card_name] = expected_value

        if not attr_prefs:
            return df

        # Filter to cards with this attribute preference
        cards_with_attr_pref = set(attr_prefs.keys())
        attr_mask = df["name"].isin(cards_with_attr_pref)

        if not attr_mask.any():
            return df

        # Get expected and actual values
        attr_df = df[attr_mask].copy()
        attr_df["expected_value"] = attr_df["name"].map(attr_prefs)
        attr_df["actual_value"] = attr_df[attribute].fillna("")

        # Check for mismatches
        mismatch_mask = attr_df["expected_value"] != attr_df["actual_value"]

        if config.strict_preferences and mismatch_mask.any():
            # Apply strict filtering
            df.loc[attr_mask & mismatch_mask, "penalty_multiplier"] = (
                config.high_cost / df.loc[attr_mask & mismatch_mask, "price"]
            )
            df.loc[attr_mask & mismatch_mask, "penalty_explanation"] = f"{attribute} mismatch (strict filter)"
        elif mismatch_mask.any():
            # Apply flexible penalties
            penalties = attr_df.loc[mismatch_mask].apply(
                lambda row: self._calculate_attribute_penalty(attribute, row["actual_value"], row["expected_value"]),
                axis=1,
            )

            # Update penalties
            mismatch_indices = attr_df.loc[mismatch_mask].index
            df.loc[mismatch_indices, "penalty_multiplier"] *= penalties

            # Update explanations
            explanations = (
                attr_df.loc[mismatch_mask, "actual_value"].astype(str)
                + " vs wanted "
                + attr_df.loc[mismatch_mask, "expected_value"].astype(str)
                + " (penalty: "
                + penalties.round(1).astype(str)
                + "x)"
            )

            current_explanations = df.loc[mismatch_indices, "penalty_explanation"]
            new_explanations = np.where(
                current_explanations == "No penalties applied",
                f"{attribute}: " + explanations,
                current_explanations + f"; {attribute}: " + explanations,
            )
            df.loc[mismatch_indices, "penalty_explanation"] = new_explanations

        return df

    def _calculate_preference_penalties(
        self, card_dict: Dict[str, Any], preferences: Dict[str, Any], config: PenaltyConfig
    ) -> Tuple[float, list[str]]:
        """Calculate preference penalties for a single card."""
        total_multiplier = 1.0
        explanations = []

        for attr in ["language", "version", "quality", "foil", "set_name"]:
            expected = preferences.get(attr)
            actual = card_dict.get(attr)

            if expected is None or expected == "":
                continue

            if actual != expected:
                penalty = self._calculate_attribute_penalty(attr, actual, expected)
                total_multiplier *= penalty

                if penalty > 1.0:
                    explanations.append(f"{attr}: {actual} vs wanted {expected} (penalty: {penalty:.1f}x)")

        return total_multiplier, explanations

    def _calculate_attribute_penalty(self, attribute: str, actual: Any, expected: Any) -> float:
        """Calculate penalty for a specific attribute mismatch."""
        try:
            if attribute == "language":
                if actual in self._language_weights and expected in self._language_weights:
                    return self._language_weights[actual] / self._language_weights[expected]
                return CardLanguage.calculate_language_preference_penalty(actual, expected)

            elif attribute == "version":
                return CardVersion.calculate_version_preference_penalty(actual, expected)

            elif attribute == "quality":
                if actual in self._quality_weights and expected in self._quality_weights:
                    return self._quality_weights[actual] / self._quality_weights[expected]
                return CardQuality.calculate_quality_preference_penalty(actual, expected)

            elif attribute == "foil":
                return 1.3 if actual != expected else 1.0

            elif attribute == "set_name":
                return 1.2 if actual != expected else 1.0

            else:
                return 1.1  # Default penalty for unknown attributes

        except Exception as e:
            logger.warning(f"Error calculating {attribute} penalty: {e}")
            return 1.1

    def _build_quality_lookup(self) -> Dict[str, float]:
        """Build quality penalty lookup table."""
        try:
            quality_weights = {}
            for quality in CardQuality:
                quality_weights[quality.value] = CardQuality.get_weight(quality.value)

            # Add common quality variations
            quality_weights.update(
                {
                    "NM": quality_weights.get("Near Mint", 1.0),
                    "LP": quality_weights.get("Light Play", 1.1),
                    "MP": quality_weights.get("Moderate Play", 1.3),
                    "HP": quality_weights.get("Heavy Play", 1.5),
                    "DMG": quality_weights.get("Damaged", 2.0),
                    "Unknown": 1.5,
                    "": 1.5,
                }
            )

            return quality_weights
        except Exception as e:
            logger.warning(f"Error building quality lookup: {e}")
            return {"NM": 1.0, "LP": 1.1, "MP": 1.3, "HP": 1.5, "DMG": 2.0}

    def _build_language_lookup(self) -> Dict[str, float]:
        """Build language penalty lookup table."""
        try:
            language_weights = {}
            languages = [
                "English",
                "French",
                "German",
                "Italian",
                "Spanish",
                "Portuguese",
                "Japanese",
                "Korean",
                "Chinese Simplified",
                "Chinese Traditional",
                "Russian",
            ]

            for lang in languages:
                try:
                    language_weights[lang] = CardLanguage.get_weight(lang)
                except:
                    language_weights[lang] = 1.0

            # Add default for unknown languages
            language_weights.update({"Unknown": 1.5, "": 1.5})

            return language_weights
        except Exception as e:
            logger.warning(f"Error building language lookup: {e}")
            return {"English": 1.0, "Unknown": 1.5}

    def _log_penalty_statistics(self, df: pd.DataFrame, has_preferences: bool):
        """Log statistics about applied penalties."""
        if not has_preferences:
            return

        pref_df = df[df["preference_applied"]]
        if pref_df.empty:
            return

        avg_penalty = pref_df["penalty_multiplier"].mean()
        max_penalty = pref_df["penalty_multiplier"].max()
        min_penalty = pref_df["penalty_multiplier"].min()

        logger.info(f"Penalty Statistics: avg={avg_penalty:.2f}x, range={min_penalty:.2f}x-{max_penalty:.2f}x")

        # Log high penalties
        high_penalty_count = (pref_df["penalty_multiplier"] > 2.0).sum()
        if high_penalty_count > 0:
            logger.warning(f"⚠️  {high_penalty_count} listings with high penalties (>2x)")

        # Log strict filter rejections
        strict_rejections = (pref_df["penalty_explanation"] == "strict_filter").sum()
        if strict_rejections > 0:
            logger.warning(f"❌ {strict_rejections} listings rejected by strict preferences")

    @staticmethod
    def create_from_config(config: Dict[str, Any]) -> "PenaltyCalculator":
        """Factory method to create penalty calculator from config."""
        return PenaltyCalculator(config)
