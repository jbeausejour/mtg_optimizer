import logging
import re
from enum import Enum
from typing import Dict

import pandas as pd

logger = logging.getLogger(__name__)

QUALITY_MAPPING: Dict[str, str] = {
    # NM variants
    "NM-Mint": "NM",
    "NM-MINT": "NM",
    "MINT/NEAR-MINT": "NM",
    "MINT/NEAR-MINT": "NM",
    "MINT/NM": "NM",
    "Near-Mint": "NM",
    "NEAR-MINT": "NM",
    "NM": "NM",
    "Brand New": "NM",
    "HERO DEAL": "NM",
    "New": "NM",
    "Mint/Near-Mint": "NM",
    "MINT/NEAR-MINT": "NM",
    "Near Mint": "NM",
    "M/NM": "NM",
    "Mint": "NM",
    # LP variants
    "LP": "LP",
    "Light Play": "LP",
    "LIGHT PLAY": "LP",
    "Lightly Played": "LP",
    "EX": "LP",
    "VG": "LP",
    "SP": "LP",
    "Slight Play": "LP",
    "SLIGHTLY PLAYED": "LP",
    # MP variants
    "MP": "MP",
    "Moderate Play": "MP",
    "MODERATE PLAY": "MP",
    "MODERATLY PLAYED": "MP",
    "Moderately Played": "MP",
    "Played": "MP",
    "GD": "MP",
    "PL": "MP",
    "PL/MP": "MP",
    # HP variants
    "HP": "HP",
    "Heavy Play": "HP",
    "HEAVY PLAY": "HP",
    "Heavy Played": "HP",
    "Heavily Played": "HP",
    "HEAVILY PLAYED": "HP",
    "PR": "HP",
    # DMG variants
    "DMG": "DMG",
    "Damaged": "DMG",
    "DAMAGED": "DMG",
    # Default case
    "": "DMG",
}

QUALITY_WEIGHTS: Dict[str, float] = {
    "NM": 1.0,
    "LP": 1.3,
    "MP": 1.7,
    "HP": 5.5,
    "DMG": 999999,
}

LANGUAGE_WEIGHTS: Dict[str, float] = {
    "English": 1.0,  # No penalty for English
    "French": 4.0,  # Medium penalty for French language
    "Unknown": 5.0,  # Heavy penalty for unknown language
    "default": 5.0,  # Heavy penalty for all non-English languages
}

LANGUAGE_MAPPING: Dict[str, str] = {
    # English variants
    "en": "English",
    "eng": "English",
    "english": "English",
    "en-us": "English",
    "anglais": "English",  # French word for English
    # Japanese variants
    "jp": "Japanese",
    "ja": "Japanese",
    "jpn": "Japanese",
    "japanese": "Japanese",
    "japonais": "Japanese",  # French word for Japanese
    # Chinese variants
    "cn": "Chinese",
    "zh": "Chinese",
    "chi": "Chinese",
    "chinese": "Chinese",
    "s-chinese": "Chinese",
    "chinois": "Chinese",  # French word for Chinese
    # Korean variants
    "kr": "Korean",
    "ko": "Korean",
    "kor": "Korean",
    "korean": "Korean",
    "coréen": "Korean",  # French word for Korean
    # Russian variants
    "ru": "Russian",
    "rus": "Russian",
    "russian": "Russian",
    "russe": "Russian",  # French word for Russian
    # German variants
    "de": "German",
    "deu": "German",
    "ger": "German",
    "german": "German",
    "allemand": "German",  # French word for German
    # Spanish variants
    "es": "Spanish",
    "esp": "Spanish",
    "spa": "Spanish",
    "spanish": "Spanish",
    "espagnol": "Spanish",  # French word for Spanish
    # French variants
    "fr": "French",
    "fra": "French",
    "fre": "French",
    "french": "French",
    "français": "French",
    # Italian variants
    "it": "Italian",
    "ita": "Italian",
    "italian": "Italian",
    "italien": "Italian",  # French word for Italian
    # Portuguese variants
    "pt": "Portuguese",
    "por": "Portuguese",
    "portuguese": "Portuguese",
    "portugais": "Portuguese",  # French word for Portuguese
    # Unknown variants
    "unknown": "Unknown",  # French word for Portuguese
}

VERSION_MAPPING: Dict[str, str] = {
    # Standard variants
    "standard": "Standard",
    "normal": "Standard",
    "regular": "Standard",
    "": "Standard",
    # Foil variants
    "foil": "Foil",
    "premium": "Foil",
    "traditional foil": "Foil",
    # Etched variants
    "etched": "Etched",
    "etched foil": "Etched",
    # Showcase variants
    "showcase": "Showcase",
    "special": "Showcase",
    # Extended art variants
    "extended": "Extended Art",
    "extended art": "Extended Art",
    "extended-art": "Extended Art",
    # Borderless variants
    "borderless": "Borderless",
    "full art": "Borderless",
    "fullart": "Borderless",
}

QUALITY_MAPPING_UPPER = {k.upper(): v for k, v in QUALITY_MAPPING.items()}


class CardQuality(str, Enum):
    """Enumeration of possible card quality values"""

    NM = "NM"
    LP = "LP"
    MP = "MP"
    HP = "HP"
    DMG = "DMG"

    @classmethod
    def get_weight(cls, quality: str) -> float:
        normalized = cls.normalize(quality)
        return QUALITY_WEIGHTS.get(normalized, QUALITY_WEIGHTS["DMG"])

    @classmethod
    def get_upper_mapping(cls):
        return QUALITY_MAPPING_UPPER

    @classmethod
    def calculate_quality_preference_penalty(cls, actual_quality: str, preferred_quality: str) -> float:
        """
        Calculate penalty based on quality preference vs actual quality.
        Better quality = no penalty, worse quality = graduated penalty
        """
        quality_order = {"NM": 0, "LP": 1, "MP": 2, "HP": 3, "DMG": 4}

        actual_rank = quality_order.get(actual_quality, 4)  # Default to DMG if unknown
        preferred_rank = quality_order.get(preferred_quality, 0)  # Default to NM if unknown

        if actual_rank <= preferred_rank:
            # Equal or better quality = no penalty
            return 1.0

        # Worse quality = graduated penalty based on steps down
        steps_worse = actual_rank - preferred_rank
        penalties = {
            1: 1.3,  # One step worse (NM->LP, LP->MP, etc.)
            2: 1.8,  # Two steps worse (NM->MP, LP->HP, etc.)
            3: 3.0,  # Three steps worse (NM->HP, LP->DMG, etc.)
            4: 5.0,  # Four steps worse (NM->DMG)
        }

        return penalties.get(steps_worse, 5.0)  # Cap at 5x penalty

    @classmethod
    def normalize(cls, quality: str) -> str:
        if not quality:
            logger.debug("Empty quality value, defaulting to NM")
            return "NM"

        quality_str = str(quality).strip().upper()

        for prefix in ("FREDERICTON: ", "FREDERICTON ", "MONCTON: "):
            if quality_str.startswith(prefix):
                quality_str = quality_str[len(prefix) :]

        if quality_str in QUALITY_MAPPING_UPPER:
            normalized = QUALITY_MAPPING_UPPER[quality_str]
            logger.debug(f"Found quality mapping: '{quality}' -> '{normalized}'")
            return normalized

        # Try a second pass with fallback cleaning
        fallback_quality = re.sub(r"[-_]", " ", quality_str).strip()
        if fallback_quality in QUALITY_MAPPING_UPPER:
            return QUALITY_MAPPING_UPPER[fallback_quality]

        logger.warning(f"No quality mapping found for '{quality}', defaulting to DMG")
        return "DMG"

    @classmethod
    def validate(cls, quality: str) -> bool:
        normalized = cls.normalize(quality)
        return normalized in {q.value for q in cls}

    @classmethod
    def validate_and_normalize(cls, quality: str) -> str:
        logger.debug(f"Validating and normalizing quality: '{quality}'")
        try:
            normalized = cls.normalize(quality)
            logger.debug(f"Normalized quality: '{normalized}'")

            if not cls.validate(normalized):
                valid_qualities = ", ".join(q.value for q in cls)
                logger.error(
                    f"Quality validation failed - '{quality}' normalized to '{normalized}' is not in valid qualities: {valid_qualities}"
                )
                raise ValueError(
                    f"Invalid quality '{quality}' (normalized: '{normalized}'). Must be one of: {valid_qualities}"
                )

            return normalized
        except Exception as e:
            logger.error(f"Error in validate_and_normalize: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def validate_and_update_qualities(df: pd.DataFrame, quality_column: str = "Quality") -> pd.DataFrame:
        """Validate and normalize quality values in DataFrame"""
        # Move the validation logic here from CardQuality class
        if quality_column not in df.columns:
            raise ValueError(f"Column {quality_column} not found in DataFrame")

        df = df.copy()
        unique_qualities = df[quality_column].dropna().unique()

        for quality in unique_qualities:
            try:
                normalized = CardQuality.validate_and_normalize(quality)
                df.loc[df[quality_column] == quality, quality_column] = normalized
            except ValueError:
                df.loc[df[quality_column] == quality, quality_column] = "DMG"

        return df


class CardLanguage(str, Enum):
    """Enumeration of possible card language values"""

    ENGLISH = "English"
    JAPANESE = "Japanese"
    CHINESE = "Chinese"
    KOREAN = "Korean"
    RUSSIAN = "Russian"
    GERMAN = "German"
    SPANISH = "Spanish"
    FRENCH = "French"
    ITALIAN = "Italian"
    PORTUGUESE = "Portuguese"
    UNKNOWN = "Unknown"

    @classmethod
    def normalize(cls, language: str) -> str:
        """Normalize language string to enum value"""
        if not language:
            return cls.UNKNOWN.value

        normalized = LANGUAGE_MAPPING.get(language.lower().strip())
        if not normalized or normalized not in {lang.value for lang in cls}:
            logger.warning(f"Invalid language '{language}', defaulting to Unknown")
            return cls.UNKNOWN.value

        return normalized

    @classmethod
    def get_language_mapping(cls):
        return LANGUAGE_MAPPING

    @classmethod
    def get_weight(cls, language: str) -> float:
        return LANGUAGE_WEIGHTS.get(language, LANGUAGE_WEIGHTS["default"])

    @classmethod
    def calculate_language_preference_penalty(cls, actual_language: str, preferred_language: str) -> float:
        """
        Calculate penalty for language preference mismatch.
        English is generally preferred, other languages get penalties when not requested.
        """
        # If they match, no penalty
        if actual_language == preferred_language:
            return 1.0

        # If user wants any language and gets English, no penalty (upgrade)
        if actual_language == "English":
            return 1.0

        # If user wants English but gets other language, apply standard language weight
        if preferred_language == "English":
            return cls.get_weight(actual_language)

        # If user wants specific non-English and gets different non-English, moderate penalty
        return 1.5


class CardVersion(str, Enum):
    """Enumeration of possible card version values"""

    STANDARD = "Standard"
    FOIL = "Foil"
    ETCHED = "Etched"
    SHOWCASE = "Showcase"
    EXTENDED_ART = "Extended Art"
    BORDERLESS = "Borderless"

    @classmethod
    def normalize(cls, version: str) -> str:
        """Normalize version string to enum value"""
        if not version:
            return cls.STANDARD.value

        version_str = str(version).lower().strip()
        normalized = VERSION_MAPPING.get(version_str, cls.STANDARD.value)

        if normalized not in {v.value for v in cls}:
            logger.debug(f"Unknown version '{version}', defaulting to Standard")
            return cls.STANDARD.value

        return normalized

    @classmethod
    def calculate_version_preference_penalty(cls, actual_version: str, preferred_version: str) -> float:
        """
        Calculate penalty for version preference mismatch.
        Premium versions (foil, etc.) when not requested get moderate penalties.
        Standard when premium requested gets higher penalty.
        """
        # If they match, no penalty
        if actual_version == preferred_version:
            return 1.0

        # Define version desirability (higher = more premium)
        version_ranks = {"Standard": 0, "Foil": 1, "Etched": 1, "Showcase": 2, "Extended Art": 2, "Borderless": 3}

        actual_rank = version_ranks.get(actual_version, 0)
        preferred_rank = version_ranks.get(preferred_version, 0)

        # Getting higher rank than requested = small penalty (might not want premium)
        if actual_rank > preferred_rank:
            return 1.2

        # Getting lower rank than requested = higher penalty
        if actual_rank < preferred_rank:
            steps_down = preferred_rank - actual_rank
            return 1.5 + (steps_down * 0.3)  # 1.5x, 1.8x, 2.1x penalties

        return 1.0
