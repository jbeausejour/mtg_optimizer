import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

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
    cards_required_total: Optional[int] = None
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
    strategy: str = Field(
        default="auto",
        description="Optimization algorithm to use",
        pattern=r"^(auto|milp|nsga2|nsga-ii|nsga3|nsga-iii|moead|hybrid|hybrid_milp_nsga3)$",
    )
    min_store: int = Field(..., gt=0)
    max_store: int = 0
    max_unique_store: int = 0
    find_min_store: bool
    buylist_id: int
    user_id: int
    weights: Optional[Dict[str, float]] = Field(
        default_factory=lambda: {"cost": 1.0, "quality": 1.0, "store_count": 0.3}
    )
    strict_preferences: bool = False
    user_preferences: Optional[Dict[str, CardPreference]] = None
    # Add enhanced optimization fields
    use_enhanced_optimization: bool = Field(default=True)
    time_limit: int = Field(default=300, ge=60, le=3600)
    max_iterations: int = Field(default=1000, ge=100, le=10000)

    # Algorithm-specific parameters
    population_size: int = Field(default=200, ge=50, le=1000)
    neighborhood_size: int = Field(default=20, ge=10, le=50)
    decomposition_method: str = Field(default="tchebycheff", pattern=r"^(tchebycheff|weighted_sum|pbi)$")
    reference_point_divisions: int = Field(default=12, ge=6, le=20)  # For NSGA-III

    @property
    def milp_strat(self) -> bool:
        return self.strategy == "milp"

    @property
    def nsga_strat(self) -> bool:
        return self.strategy in ["nsga-ii", "nsga2"]

    @property
    def nsga3_strat(self) -> bool:
        return self.strategy in ["nsga-iii", "nsga3"]

    @property
    def hybrid_strat(self) -> bool:
        return self.strategy.startswith("hybrid")

    @field_validator("strategy")
    def normalize_strategy(cls, v):
        """Normalize strategy names for compatibility"""
        if isinstance(v, str):
            v = v.lower().strip()

            # Handle common variations
            strategy_mapping = {
                "nsga-ii": "nsga2",  # Map hyphenated to underscore version
                "nsga_ii": "nsga2",
                "nsga-iii": "nsga3",  # Map hyphenated to underscore version
                "nsga_iii": "nsga3",
                "moea/d": "moead",
                "moea_d": "moead",
                "auto-select": "auto",
                "autoselect": "auto",
                "hybrid_milp_nsga_iii": "hybrid_milp_nsga3",
                "hybrid-milp-nsga-iii": "hybrid_milp_nsga3",
            }

            normalized = strategy_mapping.get(v, v)

            # Validate against allowed strategies
            allowed = ["auto", "milp", "nsga2", "nsga-ii", "nsga3", "nsga-iii", "moead", "hybrid", "hybrid_milp_nsga3"]
            if normalized not in allowed:
                # For backward compatibility, map unsupported to supported
                fallback_mapping = {
                    "genetic": "nsga2",
                    "evolutionary": "nsga3",  # Default to NSGA-III for evolutionary
                    "multi_objective": "nsga3",  # NSGA-III for multi-objective
                    "decomposition": "moead",
                    "reference_points": "nsga3",  # New mapping for reference point approaches
                }
                normalized = fallback_mapping.get(normalized, "auto")

            return normalized
        return v

    @field_validator("min_store")
    @classmethod
    def validate_min_store(cls, v: int) -> int:
        if v > 20:  # Business logic example
            raise ValueError("Cannot optimize for more than 20 stores")
        return v

    @field_validator("max_store")
    @classmethod
    def validate_max_store_greater_than_min(cls, v, info):
        """Ensure max_store >= min_store"""
        if hasattr(info, "data") and info.data and "min_store" in info.data:
            min_store_value = info.data["min_store"]
            if v > 0 and v < min_store_value:
                raise ValueError("max_store must be >= min_store")
        return v

    @field_validator("weights")
    def validate_weights(cls, v):
        """Ensure all weights are positive"""
        for key, weight in v.items():
            if weight < 0:
                raise ValueError(f"Weight for {key} must be non-negative")
        return v

    @field_validator("reference_point_divisions")
    @classmethod
    def validate_reference_points(cls, v: int) -> int:
        """Validate reference point divisions for NSGA-III"""
        if v < 6:
            logger.warning("Reference point divisions < 6 may provide insufficient diversity")
        elif v > 20:
            logger.warning("Reference point divisions > 20 may be computationally expensive")
        return v

    def get_algorithm_config(self) -> Dict[str, Any]:
        """Get algorithm-specific configuration"""
        base_config = {
            "primary_algorithm": self.strategy,
            "time_limit": self.time_limit,
            "max_iterations": self.max_iterations,
            "early_stopping": getattr(self, "early_stopping", True),
            "convergence_threshold": getattr(self, "convergence_threshold", 0.001),
            "weights": self.weights,
            "min_store": self.min_store,
            "max_store": self.max_store,
            "find_min_store": self.find_min_store,
            "strict_preferences": self.strict_preferences,
            "use_enhanced_optimization": self.use_enhanced_optimization,
        }

        # Add algorithm-specific parameters
        if self.strategy in ["nsga2", "nsga-ii", "nsga3", "nsga-iii", "moead", "hybrid", "hybrid_milp_nsga3"]:
            base_config.update(
                {
                    "population_size": self.population_size,
                    "tournament_size": getattr(self, "tournament_size", 3),
                    "crossover_probability": getattr(self, "crossover_probability", 0.8),
                    "mutation_probability": getattr(self, "mutation_probability", 0.1),
                    "elite_size": getattr(self, "elite_size", 10),
                }
            )

        if self.strategy in ["nsga3", "nsga-iii", "hybrid_milp_nsga3"]:
            base_config.update(
                {
                    "reference_point_divisions": self.reference_point_divisions,
                    "normalization_method": getattr(self, "normalization_method", "ideal_point"),
                }
            )

        if self.strategy == "moead":
            base_config.update(
                {"neighborhood_size": self.neighborhood_size, "decomposition_method": self.decomposition_method}
            )

        if self.strategy == "milp":
            base_config.update(
                {
                    "gap_tolerance": getattr(self, "milp_gap_tolerance", 0.01),
                    "threads": getattr(self, "milp_threads", -1),
                    "presolve": getattr(self, "milp_presolve", True),
                }
            )

        if self.strategy.startswith("hybrid"):
            base_config.update(
                {
                    "milp_time_fraction": getattr(self, "hybrid_milp_time_fraction", 0.3),
                    "local_search_enabled": getattr(self, "hybrid_local_search", True),
                }
            )

        return base_config

    def get_problem_characteristics(self, num_cards: int, num_stores: int) -> Dict[str, Any]:
        """Calculate problem characteristics for algorithm selection"""
        complexity_score = (num_cards * num_stores) / 1000

        return {
            "num_cards": num_cards,
            "num_stores": num_stores,
            "complexity_score": min(complexity_score, 1.0),
            "time_limit": self.time_limit,
            "strict_preferences": self.strict_preferences,
            "requires_diversity": self.strategy in ["nsga3", "nsga-iii", "hybrid_milp_nsga3"],
        }


class OptimizationResultDTO(BaseModel):
    """Enhanced optimization result with algorithm performance data"""

    status: str
    message: str
    buylist_id: Optional[int] = None
    user_id: Optional[int] = None
    sites_scraped: int = 0
    cards_scraped: int = 0
    solutions: List[OptimizationSolution] = Field(default_factory=list)
    errors: Dict[str, List[str]] = Field(
        default_factory=lambda: {"unreachable_stores": [], "unknown_languages": [], "unknown_qualities": []}
    )
    progress: int = Field(default=100, ge=0, le=100)

    # Enhanced result metadata
    algorithm_used: Optional[str] = None
    execution_time: Optional[float] = None
    iterations: Optional[int] = None
    convergence_metric: Optional[float] = None
    performance_stats: Optional[Dict[str, Any]] = None

    # Algorithm comparison data (if enabled)
    algorithm_comparison: Optional[Dict[str, Any]] = None

    def get_best_solution(self) -> Optional[OptimizationSolution]:
        """Get the best solution from the results"""
        for solution in self.solutions:
            if solution.is_best_solution:
                return solution
        return self.solutions[0] if self.solutions else None

    def get_success_rate(self) -> float:
        """Calculate success rate based on completeness"""
        if not self.solutions:
            return 0.0

        complete_solutions = [s for s in self.solutions if s.missing_cards_count == 0]
        return len(complete_solutions) / len(self.solutions)

    def get_average_execution_time(self) -> float:
        """Get average execution time across solutions"""
        times = [s.execution_time for s in self.solutions if hasattr(s, "execution_time") and s.execution_time is not None]
        return sum(times) / len(times) if times else 0.0

    @field_validator("status")
    def validate_status(cls, v):
        valid_statuses = ["Completed", "Failed", "Processing"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of {valid_statuses}")
        return v