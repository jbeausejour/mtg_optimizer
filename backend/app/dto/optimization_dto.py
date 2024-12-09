import logging
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict
from datetime import datetime
from app.constants.card_mappings import CardLanguage, CardQuality
from app.services.card_service import CardService

logger = logging.getLogger(__name__)

# Remove CardQuality class entirely as it's now in card_mappings.py

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
    set_code: str
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
    set_code: str
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

            set_name = card_data.get('set_name')
            set_code = card_data.get('set_code')
            
            if not set_code:
                logger.info(f"Attempting to get set code for set name: {set_name}")
                try:
                    set_code = CardService.get_set_code(set_name)
                    logger.info(f"Retrieved set code: {set_code} for set: {set_name}")
                except Exception as e:
                    logger.error(f"Failed to get set code for {set_name}: {str(e)}")
                    set_code = ""  # Fallback to empty string if lookup fails
            
            return {
                'name': card_data['name'],
                'site_name': card_data['site_name'],
                'price': float(card_data['price']),
                'quality': card_data['quality'],
                'quantity': int(card_data['quantity']),
                'set_name': set_name,
                'set_code': set_code,
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