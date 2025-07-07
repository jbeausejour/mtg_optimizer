# backend/app/optimization/config/algorithm_configs.py
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class AlgorithmConfig:
    """Configuration for optimization algorithms"""

    # Core parameters
    primary_algorithm: str = "milp"

    # Store constraints
    min_store: int = 1
    max_store: int = 10
    find_min_store: bool = False

    # Preferences
    strict_preferences: bool = False
    weights: Dict[str, float] = field(default_factory=lambda: {"cost": 1.0, "quality": 1.0, "store_count": 0.3})
    user_preferences: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Algorithm control
    time_limit: int = 300
    max_iterations: int = 1000
    early_stopping: bool = True
    convergence_threshold: float = 0.001

    # Algorithm-specific parameters
    population_size: int = 200  # For evolutionary algorithms
    neighborhood_size: int = 20  # For MOEA/D
    decomposition_method: str = "tchebycheff"  # For MOEA/D
    milp_gap_tolerance: float = 0.01  # For MILP
    hybrid_milp_time_fraction: float = 0.3  # For hybrid algorithms
    reference_point_divisions: int = 12  # For NSGA-III

    # Parallelization
    n_jobs: int = -1  # Use all available cores

    @classmethod
    def from_optimization_config(cls, opt_config) -> "AlgorithmConfig":
        """Create AlgorithmConfig from OptimizationConfigDTO or dict"""
        if hasattr(opt_config, "to_dict"):
            # It's a DTO
            config_dict = opt_config.to_dict()
        else:
            # It's already a dict
            config_dict = opt_config if isinstance(opt_config, dict) else {}

        # Map strategy to primary_algorithm if needed
        primary_algorithm = config_dict.get("primary_algorithm") or config_dict.get("strategy", "milp")

        # Create instance with mapped values
        return cls(
            primary_algorithm=primary_algorithm,
            min_store=config_dict.get("min_store", 1),
            max_store=config_dict.get("max_store", 10),
            find_min_store=config_dict.get("find_min_store", False),
            strict_preferences=config_dict.get("strict_preferences", False),
            weights=config_dict.get("weights", cls.__dataclass_fields__["weights"].default_factory()),
            user_preferences=config_dict.get("user_preferences", {}),
            time_limit=config_dict.get("time_limit", 300),
            max_iterations=config_dict.get("max_iterations", 1000),
            early_stopping=config_dict.get("early_stopping", True),
            convergence_threshold=config_dict.get("convergence_threshold", 0.001),
            population_size=config_dict.get("population_size", 200),
            neighborhood_size=config_dict.get("neighborhood_size", 20),
            decomposition_method=config_dict.get("decomposition_method", "tchebycheff"),
            milp_gap_tolerance=config_dict.get("milp_gap_tolerance", 0.01),
            hybrid_milp_time_fraction=config_dict.get("hybrid_milp_time_fraction", 0.3),
            reference_point_divisions=config_dict.get("reference_point_divisions", 12),
            n_jobs=config_dict.get("n_jobs", -1),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "primary_algorithm": self.primary_algorithm,
            "min_store": self.min_store,
            "max_store": self.max_store,
            "find_min_store": self.find_min_store,
            "strict_preferences": self.strict_preferences,
            "weights": self.weights,
            "user_preferences": self.user_preferences,
            "time_limit": self.time_limit,
            "max_iterations": self.max_iterations,
            "early_stopping": self.early_stopping,
            "convergence_threshold": self.convergence_threshold,
            "population_size": self.population_size,
            "neighborhood_size": self.neighborhood_size,
            "decomposition_method": self.decomposition_method,
            "milp_gap_tolerance": self.milp_gap_tolerance,
            "hybrid_milp_time_fraction": self.hybrid_milp_time_fraction,
            "reference_point_divisions": self.reference_point_divisions,
            "n_jobs": self.n_jobs,
        }

    def get_algorithm_specific_params(self, algorithm: str) -> Dict[str, Any]:
        """Get parameters specific to an algorithm"""
        params = {
            "time_limit": self.time_limit,
            "max_iterations": self.max_iterations,
            "early_stopping": self.early_stopping,
            "convergence_threshold": self.convergence_threshold,
        }

        if algorithm in ["nsga2", "nsga3", "moead"]:
            params["population_size"] = self.population_size

        if algorithm in ["nsga3"]:
            params["reference_point_divisions"] = self.reference_point_divisions

        if algorithm == "moead":
            params["neighborhood_size"] = self.neighborhood_size
            params["decomposition_method"] = self.decomposition_method

        if algorithm == "milp":
            params["milp_gap_tolerance"] = self.milp_gap_tolerance

        if algorithm.startswith("hybrid"):
            params["hybrid_milp_time_fraction"] = self.hybrid_milp_time_fraction
            
            # Add specific parameters for hybrid variants
            if algorithm == "hybrid_milp_nsga3":
                params["reference_point_divisions"] = self.reference_point_divisions

        return params


# Default configurations for different problem sizes
SMALL_PROBLEM_CONFIG = AlgorithmConfig(
    primary_algorithm="milp",
    time_limit=60,
    max_iterations=100,
)

MEDIUM_PROBLEM_CONFIG = AlgorithmConfig(
    primary_algorithm="hybrid_milp_moead",
    time_limit=180,
    max_iterations=500,
    population_size=100,
)

LARGE_PROBLEM_CONFIG = AlgorithmConfig(
    primary_algorithm="nsga3",  # Use NSGA-III for large problems
    time_limit=300,
    max_iterations=1000,
    population_size=300,
    reference_point_divisions=12,
)

VERY_LARGE_PROBLEM_CONFIG = AlgorithmConfig(
    primary_algorithm="hybrid_milp_nsga3",  # Use hybrid for very large problems
    time_limit=600,
    max_iterations=1500,
    population_size=400,
    reference_point_divisions=15,
)

FAST_CONFIG = AlgorithmConfig(
    primary_algorithm="nsga2",
    time_limit=30,
    max_iterations=200,
    population_size=50,
    early_stopping=True,
    convergence_threshold=0.01,
)

# Specialized NSGA-III configurations
DIVERSITY_FOCUSED_CONFIG = AlgorithmConfig(
    primary_algorithm="nsga3",
    time_limit=400,
    max_iterations=1200,
    population_size=300,
    reference_point_divisions=15,  # More reference points for better diversity
    early_stopping=False,  # Let it run longer for diversity
)

HYBRID_NSGA3_CONFIG = AlgorithmConfig(
    primary_algorithm="hybrid_milp_nsga3",
    time_limit=500,
    max_iterations=1000,
    population_size=350,
    reference_point_divisions=12,
    hybrid_milp_time_fraction=0.2,  # Less time on MILP, more on NSGA-III
)