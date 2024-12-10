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

    def format_solutions(self, solutions, iterations=None):
        """Format solutions from either MILP or NSGA-II optimization"""
        formatted_solutions = []
        
        # Handle MILP solutions (DataFrame converted to dict)
        if solutions and isinstance(solutions[0], dict) and 'site_id' in solutions[0]:
            solution_by_site = {}
            for item in solutions:
                site_id = item['site_id']
                if site_id not in solution_by_site:
                    solution_by_site[site_id] = []
                solution_by_site[site_id].append({
                    'name': item['name'],
                    'quantity': int(item['quantity']),
                    'price': float(item['price']),
                    'set_name': item['set_name'],
                    'set_code': item['set_code'],
                    'quality': item['quality'],
                    'language': item.get('language', 'English'),
                    'version': item.get('version', 'Standard'),
                    'foil': bool(item.get('foil', False))
                })
            
            # Create single solution for MILP
            total_price = sum(float(item['price']) * int(item['quantity']) for item in solutions)
            formatted_solutions.append({
                'total_price': total_price,
                'num_stores': len(solution_by_site),
                'stores': [{
                    'site_id': site_id,
                    'cards': cards
                } for site_id, cards in solution_by_site.items()]
            })
            
        # Handle NSGA-II solutions (list of solutions from pareto front)
        elif solutions and isinstance(solutions, list):
            for solution in solutions:
                solution_by_site = {}
                total_price = 0
                
                for card in solution:
                    site_id = card['site_id']
                    if site_id not in solution_by_site:
                        solution_by_site[site_id] = []
                    
                    card_price = float(card['price']) * int(card['quantity'])
                    total_price += card_price
                    
                    solution_by_site[site_id].append({
                        'name': card['name'],
                        'quantity': int(card['quantity']),
                        'price': float(card['price']),
                        'set_name': card['set_name'],
                        'set_code': card['set_code'],
                        'quality': card['quality'],
                        'language': card.get('language', 'English'),
                        'version': card.get('version', 'Standard'),
                        'foil': bool(card.get('foil', False))
                    })
                
                formatted_solutions.append({
                    'total_price': total_price,
                    'num_stores': len(solution_by_site),
                    'stores': [{
                        'site_id': site_id,
                        'cards': cards
                    } for site_id, cards in solution_by_site.items()]
                })
        
        self.optimization = {
            'solutions': formatted_solutions,
            'iterations': iterations or []
        }

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