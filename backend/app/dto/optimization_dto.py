import logging
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

# Quality mapping for standardization across the application
QUALITY_MAPPING = {
    # NM variants
    "NM-Mint": "NM", 
    "NM-MINT": "NM",
    "MINT/NEAR-MINT": "NM",  # Add this line
    "Mint/Near-Mint": "NM",
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
    "SLIGHTLY PLAYED": "LP",  
    # MP variants
    "MP": "MP",
    "Moderate Play": "MP", 
    "MODERATE PLAY": "MP", 
    "MODERATLY PLAYED": "MP", 
    "Moderately Played": "MP",
    "GD": "MP",  
    "PL": "MP",  
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
    "": "DMG"  
}

# Quality weights for price adjustments
QUALITY_WEIGHTS = {
    "NM": 1.0,
    "LP": 1.3,
    "MP": 1.7,
    "HP": 2.5,
    "DMG": 999999
}

LANGUAGE_MAPPING = {
    # English variants
    'en': 'English',
    'eng': 'English',
    'english': 'English',
    'en-us': 'English',
    'anglais': 'English',  # French word for English
    # Japanese variants
    'jp': 'Japanese',
    'ja': 'Japanese',
    'jpn': 'Japanese',
    'japanese': 'Japanese',
    'japonais': 'Japanese',  # French word for Japanese
    # Chinese variants
    'cn': 'Chinese',
    'zh': 'Chinese',
    'chi': 'Chinese',
    'chinese': 'Chinese',
    's-chinese': 'Chinese',
    'chinois': 'Chinese',  # French word for Chinese
    # Korean variants
    'kr': 'Korean',
    'ko': 'Korean',
    'kor': 'Korean',
    'korean': 'Korean',
    'coréen': 'Korean',  # French word for Korean
    # Russian variants
    'ru': 'Russian',
    'rus': 'Russian',
    'russian': 'Russian',
    'russe': 'Russian',  # French word for Russian
    # German variants
    'de': 'German',
    'deu': 'German',
    'ger': 'German',
    'german': 'German',
    'allemand': 'German',  # French word for German
    # Spanish variants
    'es': 'Spanish',
    'esp': 'Spanish',
    'spa': 'Spanish',
    'spanish': 'Spanish',
    'espagnol': 'Spanish',  # French word for Spanish
    # French variants
    'fr': 'French',
    'fra': 'French',
    'fre': 'French',
    'french': 'French',
    'français': 'French',
    # Italian variants
    'it': 'Italian',
    'ita': 'Italian',
    'italian': 'Italian',
    'italien': 'Italian',  # French word for Italian
    # Portuguese variants
    'pt': 'Portuguese',
    'por': 'Portuguese',
    'portuguese': 'Portuguese',
    'portugais': 'Portuguese',  # French word for Portuguese
    # Unknown variants
    'unknown': 'Unknown',  # French word for Portuguese
}

logger = logging.getLogger(__name__)

class CardQuality(str, Enum):
    """Enumeration of possible card quality values"""
    NM = "NM"
    LP = "LP"
    MP = "MP"
    HP = "HP"  
    DMG = "DMG"

    @classmethod
    def get_weight(cls, quality: str) -> float:
        """Get weight for price adjustment based on card quality"""
        normalized = cls.normalize(quality)
        return QUALITY_WEIGHTS.get(normalized, QUALITY_WEIGHTS["DMG"])

    @classmethod
    def normalize(cls, quality: str) -> str:
        """Normalize quality string to standard enum value"""
        
        if not quality:
            logger.debug("Empty quality value, defaulting to NM")
            return "NM"
            
        # Convert input quality to string and uppercase
        quality_str = str(quality).strip().upper()
        
        # Create uppercase version of mapping for case-insensitive comparison
        upper_mapping = {k.upper(): v for k, v in QUALITY_MAPPING.items()}
        
        # Try to find direct match in uppercase mapping
        if quality_str in upper_mapping:
            normalized = upper_mapping[quality_str]
            logger.debug(f"Found quality mapping: '{quality}' -> '{normalized}'")
            return normalized
                
        # If no match found, log warning and return DMG
        logger.warning(f"No quality mapping found for '{quality}', defaulting to DMG")
        return "DMG"

    @classmethod
    def validate(cls, quality: str) -> bool:
        """Validate if a quality value is valid after normalization"""
        normalized = cls.normalize(quality)
        return normalized in {q.value for q in cls}

    @classmethod
    def validate_and_normalize(cls, quality: str) -> str:
        """Validate and normalize quality string, raising error if invalid"""
        logger.debug(f"Validating and normalizing quality: '{quality}'")
        try:
            normalized = cls.normalize(quality)
            logger.debug(f"Normalized quality: '{normalized}'")
            
            if not cls.validate(normalized):
                valid_qualities = ", ".join(q.value for q in cls)
                logger.error(f"Quality validation failed - '{quality}' normalized to '{normalized}' is not in valid qualities: {valid_qualities}")
                raise ValueError(f"Invalid quality '{quality}' (normalized: '{normalized}'). Must be one of: {valid_qualities}")
                
            return normalized
        except Exception as e:
            logger.error(f"Error in validate_and_normalize: {str(e)}", exc_info=True)
            raise

    @classmethod
    def update_mapping(cls, quality: str, mapped_quality: str) -> None:
        """Update the quality mapping dictionary with a new mapping"""
        if mapped_quality not in {q.value for q in cls}:
            raise ValueError(f"Invalid mapped quality: {mapped_quality}. Must be one of {[q.value for q in cls]}")
        QUALITY_MAPPING[quality] = mapped_quality
        logger.info(f"Added new quality mapping: {quality} -> {mapped_quality}")

    @classmethod
    def validate_and_update_qualities(cls, df: pd.DataFrame, quality_column: str = "Quality", interactive: bool = False) -> pd.DataFrame:
        """Validate quality values in DataFrame and optionally update mappings."""
        if quality_column not in df.columns:
            logger.error(f"Column '{quality_column}' not found in DataFrame. Available columns: {df.columns.tolist()}")
            raise ValueError(f"Column {quality_column} not found in DataFrame")

        # Create a copy to avoid modifying the original
        df = df.copy()
        
        # Find unmapped qualities
        unique_qualities = df[quality_column].dropna().unique()
        # logger.info(f"Found unique qualities in DataFrame: {unique_qualities.tolist()}")
        
        for quality in unique_qualities:
            logger.debug(f"Processing quality value: '{quality}'")
            try:
                normalized = cls.validate_and_normalize(quality)
                # Update all matching values in the DataFrame
                df.loc[df[quality_column] == quality, quality_column] = normalized
                logger.debug(f"Successfully normalized '{quality}' to '{normalized}'")
            except ValueError as e:
                logger.warning(f"Quality normalization failed for '{quality}': {str(e)}")
                if interactive:
                    # ...existing interactive code...
                    pass
                else:
                    logger.warning(f"Automatically mapping unknown quality '{quality}' to 'DMG'")
                    df.loc[df[quality_column] == quality, quality_column] = "DMG"

        # Verify final qualities
        # final_qualities = df[quality_column].unique()
        # logger.info(f"Final unique qualities after normalization: {final_qualities.tolist()}")
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

class CardValidation(BaseModel):
    """Base validation rules for card-related DTOs"""
    price: float = Field(0.0, ge=0)
    quantity: int = Field(0, ge=0)

    @field_validator('price')
    @classmethod
    def validate_price(cls, v: float) -> float:
        """Additional price validation beyond Field constraints"""
        if v > 100000:  # Example of additional business logic
            raise ValueError('Price seems unreasonably high')
        return v

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        """Additional quantity validation beyond Field constraints"""
        if v > 100:  # Example of business logic
            raise ValueError('Quantity exceeds reasonable limits')
        return v

    model_config = {
        "validate_assignment": True
    }

class CardInSolution(BaseModel):
    name: str
    site_name: str
    price: float
    quality: str
    quantity: int
    set_name: str
    version: str = Field(default="Standard")
    foil: bool = False
    language: str = "English"
    site_id: Optional[int] = None

    class Config:
        from_attributes = True

class CardOptimizationDTO(CardValidation):
    """DTO for card optimization data"""
    name: str = Field(..., min_length=1)
    site_id: int = Field(..., gt=0)
    site_name: str
    set_name: str
    quality: CardQuality = CardQuality.NM
    foil: bool = False
    language: CardLanguage = CardLanguage.ENGLISH

    @field_validator('quality')
    @classmethod
    def normalize_quality(cls, v: str) -> str:
        """Normalize the quality value using the mapping"""
        if isinstance(v, str):
            return CardQuality.normalize(v)
        return v

    def get_adjusted_price(self) -> float:
        """Calculate price adjusted by quality weight"""
        return self.price * CardQuality.get_weight(self.quality)

    @model_validator(mode='after')
    def validate_card_details(self) -> 'CardOptimizationDTO':
        """Validate relationships between fields"""
        if self.price > 0 and self.quantity == 0:
            raise ValueError("Cards with price must have quantity")
        return self

class OptimizationSolution(BaseModel):
    total_price: float
    number_store: int
    nbr_card_in_solution: int
    total_qty: Optional[int] = None
    list_stores: str
    missing_cards: List[str]
    missing_cards_count: int
    cards: Dict[str, CardInSolution]
    is_best_solution: bool = False

    class Config:
        from_attributes = True

class OptimizationConfigDTO(BaseModel):
    strategy: str = Field(..., pattern='^(milp|nsga-ii|hybrid)$')
    min_store: int = Field(..., gt=0)
    find_min_store: bool

    @field_validator('strategy')
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        valid_strategies = ['milp', 'nsga-ii', 'hybrid']
        if v not in valid_strategies:
            raise ValueError(f'Strategy must be one of {valid_strategies}')
        return v

    @field_validator('min_store')
    @classmethod
    def validate_min_store(cls, v: int) -> int:
        if v > 20:  # Business logic example
            raise ValueError('Cannot optimize for more than 20 stores')
        return v

class OptimizationResultDTO(BaseModel):
    status: str
    message: str
    sites_scraped: int
    cards_scraped: int
    solutions: List[OptimizationSolution]
    errors: Dict[str, List[str]] = Field(
        default_factory=lambda: {
            'unreachable_stores': [],
            'unknown_languages': [],
            'unknown_qualities': []
        }
    )
    progress: int = 100

    def format_from_milp(self, best_solution, all_iterations) -> None:
        """Format MILP optimization results into DTO structure"""
        logger.info(f"Formatting MILP results:")
        logger.info(f"Best solution type: {type(best_solution)}")
        logger.info(f"Best solution length: {len(best_solution) if best_solution else 0}")
        logger.info(f"Iterations length: {len(all_iterations) if all_iterations else 0}")

        self.solutions = []

        def create_card_dict(card_data):
            """Helper to create standardized card dictionary with defaults"""
            # Ensure version is never None
            version = card_data.get('version')
            if version is None or version == "":
                version = 'Standard'
                
            return {
                'name': card_data['name'],
                'site_name': card_data['site_name'],
                'price': float(card_data['price']),
                'quality': card_data['quality'],
                'quantity': int(card_data['quantity']),
                'set_name': card_data['set_name'],
                'version': version,
                'foil': bool(card_data.get('foil', False)),
                'language': card_data.get('language', 'English'),
                'site_id': card_data.get('site_id')
            }

        if best_solution:
            # Debug the card data structure
            logger.info("Sample card data from best solution:")
            if best_solution:
                logger.info(f"First card: {best_solution[0]}")
            
            try:
                # Create cards dictionary for best solution
                cards = {
                    str(i): CardInSolution(**create_card_dict(card))
                    for i, card in enumerate(best_solution)
                }
            except Exception as e:
                logger.error(f"Error creating cards dictionary: {str(e)}", exc_info=True)
                logger.info(f"all cards: {best_solution}")

            # Debug the created cards dictionary
            logger.info(f"Created cards dictionary with {len(cards)} entries")
            if cards:
                logger.info(f"Sample card entry: {next(iter(cards.values())).model_dump()}")

            # Get the corresponding iteration data
            solution_index = next((i for i, solution in enumerate(all_iterations)
                                if solution['total_price'] == best_solution[0]['price']), 0)
            best_iteration = all_iterations[solution_index]

            self.solutions.append(OptimizationSolution(
                total_price=float(best_iteration['total_price']),
                number_store=best_iteration['number_store'],
                nbr_card_in_solution=best_iteration['nbr_card_in_solution'],
                total_qty=best_iteration.get('total_qty'),
                list_stores=best_iteration['list_stores'],
                missing_cards=best_iteration.get('missing_cards', []),
                missing_cards_count=len(best_iteration.get('missing_cards', [])),
                cards=cards,
                is_best_solution=True
            ))

        if all_iterations:
            for iteration in all_iterations:
                if iteration != best_solution:  # Skip the best solution as it's already added
                    # Create cards dictionary for each iteration
                    try:
                        cards = {
                            str(i): CardInSolution(**create_card_dict(card))
                            for i, card in enumerate(iteration['sorted_results_df'])
                        }
                        
                    except Exception as e:
                        logger.error(f"Error creating cards dictionary: {str(e)}", exc_info=True)
                        logger.info(f"all cards (iterations): {iteration['sorted_results_df']}")

                    self.solutions.append(OptimizationSolution(
                        total_price=float(iteration['total_price']),
                        number_store=iteration['number_store'],
                        nbr_card_in_solution=iteration['nbr_card_in_solution'],
                        total_qty=iteration.get('total_qty'),
                        list_stores=iteration['list_stores'],
                        missing_cards=iteration.get('missing_cards', []),
                        missing_cards_count=len(iteration.get('missing_cards', [])),
                        cards=cards,
                        is_best_solution=False
                    ))
        logger.debug(f"Formatted {len(self.solutions)} solutions")

    def model_dump(self):
        return {
            'status': self.status,
            'message': self.message,
            'sites_scraped': self.sites_scraped,
            'cards_scraped': self.cards_scraped,
            'optimization': {
                'solutions': [solution.model_dump() for solution in self.solutions],
                'errors': self.errors
            },
            'progress': self.progress
        }

class ScanResultDTO(CardValidation):
    scan_id: int = Field(..., gt=0) 
    name: str = Field(..., min_length=1)
    site_id: int = Field(..., gt=0)
    set_name: str
    version: str = "Standard"
    foil: bool = False
    quality: CardQuality = CardQuality.NM
    language: CardLanguage = CardLanguage.ENGLISH
    updated_at: Optional[datetime] = None

    @classmethod
    def from_scan_result(cls, scan_result):
        """Convert a ScanResult model instance to DTO with validation"""
        try:
            # Get scan_id - try both 'scan_id' and 'id' attributes
            scan_id = getattr(scan_result, 'scan_id', None) or getattr(scan_result, 'id', None)
            if not scan_id:
                raise ValueError("scan_id is required and must be > 0")
                
            # Pre-process quality to ensure it's normalized
            raw_quality = getattr(scan_result, 'quality', CardQuality.NM)
            try:
                normalized_quality = CardQuality.validate_and_normalize(raw_quality)
            except ValueError as e:
                logger.warning(f"Quality validation failed for scan_id {scan_id}: {e}")
                normalized_quality = "DMG"  # Default to most conservative quality
            
            if normalized_quality not in [q.value for q in CardQuality]:
                raise ValueError(f"Invalid quality '{raw_quality}' normalized to '{normalized_quality}'. Must be one of: {', '.join([q.value for q in CardQuality])}")

            data = {
                'scan_id': scan_id,
                'name': getattr(scan_result, 'name', ''),
                'site_id': getattr(scan_result, 'site_id', 0),
                'price': float(getattr(scan_result, 'price', 0)),
                'set_name': getattr(scan_result, 'set_name', ''),
                'version': getattr(scan_result, 'version', 'Standard'),
                'foil': getattr(scan_result, 'foil', False),
                'quality': normalized_quality,
                'language': getattr(scan_result, 'language', CardLanguage.ENGLISH),
                'quantity': getattr(scan_result, 'quantity', 0),
                'updated_at': getattr(scan_result, 'updated_at', None)
            }
            
            return cls(**data)
        except Exception as e:
            raise ValueError(f"Invalid scan result data: {str(e)}")

    def model_dump(self):
        """Convert validated DTO to dictionary"""
        return super().model_dump(exclude_none=True)

    def to_dict(self):
        """Alias for model_dump to maintain compatibility"""
        return self.model_dump()