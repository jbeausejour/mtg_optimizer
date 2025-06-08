from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class AlgorithmConfig:
    """Comprehensive configuration for optimization algorithms"""

    # Algorithm selection
    primary_algorithm: str = "auto"
    fallback_algorithm: str = "milp"

    # General optimization settings
    time_limit_seconds: int = 300
    max_iterations: int = 1000
    convergence_tolerance: float = 1e-6

    # MILP settings
    milp_time_limit: int = 120
    milp_gap_tolerance: float = 0.01
    milp_presolve: bool = True
    milp_cuts: bool = True

    # Evolutionary algorithm settings
    population_size: int = 200
    max_generations: int = 150
    convergence_patience: int = 25

    # MOEA/D specific
    neighborhood_size: int = 20
    decomposition_method: str = "tchebycheff"
    weight_vector_generation: str = "das_dennis"

    # NSGA settings
    tournament_size: int = 5
    crossover_probability: float = 0.9
    mutation_probability: float = 0.1

    # Hybrid settings
    milp_seed_enabled: bool = True
    local_search_enabled: bool = True
    verification_enabled: bool = False

    # Performance settings
    parallel_evaluation: bool = True
    max_workers: Optional[int] = None
    caching_enabled: bool = True
    cache_size: int = 50000

    # Problem-specific settings
    strict_preferences: bool = False
    quality_weight_adjustment: float = 1.0
    store_consolidation_preference: float = 0.5

    @classmethod
    def from_optimization_config(cls, opt_config) -> "AlgorithmConfig":
        """Convert from existing OptimizationConfigDTO"""

        # Map legacy strategy to new algorithm names
        primary_algorithm = "auto"
        if hasattr(opt_config, "hybrid_strat") and opt_config.hybrid_strat:
            primary_algorithm = "hybrid_milp_moead"
        elif hasattr(opt_config, "milp_strat") and opt_config.milp_strat:
            primary_algorithm = "milp"
        elif hasattr(opt_config, "nsga_strat") and opt_config.nsga_strat:
            primary_algorithm = "moead"  # Upgrade NSGA-II to MOEA/D

        # Extract weights and other settings
        weights = getattr(opt_config, "weights", {})

        return cls(
            primary_algorithm=primary_algorithm,
            strict_preferences=getattr(opt_config, "strict_preferences", False),
            population_size=weights.get("population_size", 200),
            max_generations=weights.get("max_generations", 150),
            milp_time_limit=weights.get("milp_time_limit", 120),
            caching_enabled=weights.get("caching_enabled", True),
        )

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "AlgorithmConfig":
        """Create from dictionary"""
        return cls(**{k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for optimizer consumption"""
        return asdict(self)

    def update_from_dict(self, updates: Dict[str, Any]):
        """Update configuration from dictionary"""
        for key, value in updates.items():
            if hasattr(self, key):
                setattr(self, key, value)
