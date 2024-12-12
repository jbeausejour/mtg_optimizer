import logging
import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Optional, List, Dict
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
    optimization: Dict[str, Any] = Field(default_factory=dict)  # Add this field


    def format_solutions(self, solutions, iterations=None):
        """Format solutions from either MILP or NSGA-II optimization"""
        try:
            formatted_solutions = []
            
            if not solutions:
                logger.warning("No solutions provided to format")
                self.optimization = {
                    'solutions': [],
                    'iterations': [],
                    'errors': self.errors
                }
                return

            # Check if this is a result with explicit status
            if isinstance(solutions, dict) and 'status' in solutions:
                if solutions['status'] == 'failed':
                    logger.warning("Received failed optimization result")
                    self.optimization = {
                        'solutions': [],
                        'iterations': [],
                        'errors': solutions.get('errors', self.errors)
                    }
                    return

                solutions = solutions.get('best_solution', [])

            # Handle MILP or NSGA solutions
            for solution in (solutions if isinstance(solutions, list) else [solutions]):
                try:
                    solution_by_site = {}
                    total_price = 0.0
                    total_cards = 0
                    site_names = set()

                    # Process each card in the solution
                    for card in (solution if isinstance(solution, list) else [solution]):
                        if not isinstance(card, dict):
                            continue

                        site_id = card.get('site_id')
                        site_name = card.get('site_name')
                        
                        if site_id is None and site_name:
                            # Try to find site_id from name if missing
                            from app.models import Site
                            site = Site.query.filter_by(name=site_name).first()
                            site_id = site.id if site else None

                        if site_id not in solution_by_site:
                            solution_by_site[site_id] = []

                        # Calculate card price
                        quantity = int(card.get('quantity', 1))
                        price = float(card.get('price', 0.0))
                        card_total = price * quantity
                        
                        # Update totals
                        total_price += card_total
                        total_cards += quantity
                        if site_name:
                            site_names.add(site_name)

                        # Format card data
                        formatted_card = {
                            'name': card.get('name', ''),
                            'quantity': quantity,
                            'price': price,
                            'total_price': card_total,
                            'set_name': card.get('set_name', ''),
                            'set_code': card.get('set_code', ''),
                            'quality': card.get('quality', 'NM'),
                            'language': card.get('language', 'English'),
                            'version': card.get('version', 'Standard'),
                            'foil': bool(card.get('foil', False))
                        }
                        
                        solution_by_site[site_id].append(formatted_card)

                    # Create formatted solution
                    formatted_solution = {
                        'total_price': total_price,
                        'number_store': len(solution_by_site),
                        'nbr_card_in_solution': total_cards,
                        'list_stores': ', '.join(sorted(site_names)),
                        'stores': [
                            {
                                'site_id': site_id,
                                'cards': cards
                            }
                            for site_id, cards in solution_by_site.items()
                            if site_id is not None
                        ]
                    }
                    
                    formatted_solutions.append(formatted_solution)

                except Exception as e:
                    logger.error(f"Error formatting individual solution: {str(e)}")
                    continue

            # Format iterations if provided
            formatted_iterations = []
            if iterations:
                for iteration in iterations:
                    try:
                        if isinstance(iteration, dict) and 'sorted_results_df' in iteration:
                            formatted_iteration = {
                                'total_price': float(iteration.get('total_price', 0.0)),
                                'number_store': int(iteration.get('number_store', 0)),
                                'nbr_card_in_solution': int(iteration.get('nbr_card_in_solution', 0)),
                                'list_stores': iteration.get('list_stores', '')
                            }
                            formatted_iterations.append(formatted_iteration)
                    except Exception as e:
                        logger.error(f"Error formatting iteration: {str(e)}")
                        continue

            self.optimization = {
                'solutions': formatted_solutions,
                'iterations': formatted_iterations,
                'errors': self.errors
            }

        except Exception as e:
            logger.error(f"Error in format_solutions: {str(e)}")
            self.optimization = {
                'solutions': [],
                'iterations': [],
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