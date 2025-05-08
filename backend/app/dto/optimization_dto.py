import logging
from datetime import datetime
from typing import Dict, List, Optional

from app.constants.card_mappings import CardLanguage, CardQuality
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class CardValidation(BaseModel):
    """Base validation rules for card-related DTOs"""

    price: float = Field(0.0, ge=0)
    quantity: int = Field(0, ge=0)

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v > 100000:
            raise ValueError("Price seems unreasonably high")
        return v

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v > 100:
            raise ValueError("Quantity exceeds reasonable limits")
        return v

    model_config = {"validate_assignment": True}


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
            scan_id = getattr(scan_result, "scan_id", None) or getattr(scan_result, "id", None)
            if not scan_id:
                raise ValueError("scan_id is required and must be > 0")

            raw_quality = getattr(scan_result, "quality", CardQuality.NM)
            try:
                normalized_quality = CardQuality.validate_and_normalize(raw_quality)
            except ValueError as e:
                logger.warning(f"Quality validation failed for scan_id {scan_id}: {e}")
                normalized_quality = "DMG"  # Default to most conservative quality

            if normalized_quality not in [q.value for q in CardQuality]:
                raise ValueError(
                    f"Invalid quality '{raw_quality}' normalized to '{normalized_quality}'. Must be one of: {', '.join([q.value for q in CardQuality])}"
                )

            data = {
                "scan_id": scan_id,
                "name": getattr(scan_result, "name", ""),
                "site_id": getattr(scan_result, "site_id", 0),
                "price": float(getattr(scan_result, "price", 0)),
                "set_name": getattr(scan_result, "set_name", ""),
                "version": getattr(scan_result, "version", "Standard"),
                "foil": getattr(scan_result, "foil", False),
                "quality": normalized_quality,
                "language": getattr(scan_result, "language", CardLanguage.ENGLISH),
                "quantity": getattr(scan_result, "quantity", 0),
                "updated_at": getattr(scan_result, "updated_at", None),
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


class CardInSolution(BaseModel):
    name: str
    site_name: str
    price: float
    quality: str
    quantity: int
    set_name: str
    set_code: str
    version: str = Field(default="Standard")
    foil: bool = Field(default=False)
    language: str = "English"
    variant_id: int
    site_id: Optional[int] = None

    class Config:
        from_attributes = True


class StoreInSolution(BaseModel):
    site_id: Optional[int]
    site_name: str
    cards: List[CardInSolution]

    class Config:
        from_attributes = True


class OptimizationSolution(BaseModel):
    total_price: float
    number_store: int
    nbr_card_in_solution: int
    total_qty: Optional[int] = None
    list_stores: str
    missing_cards: List[str]
    missing_cards_count: int
    stores: List[StoreInSolution]
    is_best_solution: bool = False

    class Config:
        from_attributes = True


class CardPreference(BaseModel):
    set_name: Optional[str] = None
    language: Optional[str] = "English"
    quality: Optional[str] = "NM"
    version: Optional[str] = "Standard"
    foil: Optional[bool] = False


class OptimizationConfigDTO(BaseModel):
    strategy: str = Field(..., pattern="^(milp|nsga-ii|hybrid)$")
    min_store: int = Field(..., gt=0)
    find_min_store: bool
    buylist_id: int
    user_id: int
    strict_preferences: bool = False
    user_preferences: Optional[Dict[str, CardPreference]] = None

    @field_validator("strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        valid_strategies = ["milp", "nsga-ii", "hybrid"]
        if v not in valid_strategies:
            raise ValueError(f"Strategy must be one of {valid_strategies}")
        return v

    @field_validator("min_store")
    @classmethod
    def validate_min_store(cls, v: int) -> int:
        if v > 20:  # Business logic example
            raise ValueError("Cannot optimize for more than 20 stores")
        return v


class OptimizationResultDTO(BaseModel):
    status: str
    message: str
    buylist_id: int
    user_id: int
    sites_scraped: int
    cards_scraped: int
    solutions: List[OptimizationSolution]
    errors: Dict[str, List[str]] = Field(
        default_factory=lambda: {"unreachable_stores": [], "unknown_languages": [], "unknown_qualities": []}
    )
    progress: int = Field(default=100, ge=0, le=100)

    @field_validator("status")
    def validate_status(cls, v):
        valid_statuses = ["Completed", "Failed", "Processing"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v
