# backend/app/optimization/algorithms/factory.py
import logging
from typing import Dict, Any, Type, Optional

from ..core.base_optimizer import BaseOptimizer
from .milp.milp_optimizer import MILPOptimizer
from .evolutionary.nsga2_optimizer import NSGA2Optimizer
from .evolutionary.nsga3_optimizer import NSGA3Optimizer
from .evolutionary.moead_optimizer import MOEADOptimizer
from .hybrid.milp_moead_hybrid import HybridMILPMOEADOptimizer
from .hybrid.milp_nsga3_hybrid import HybridMILPNSGA3Optimizer

logger = logging.getLogger(__name__)


class OptimizerFactory:
    """Factory class for creating optimization algorithm instances"""

    # Registry of available optimizers
    _optimizers: Dict[str, Type[BaseOptimizer]] = {
        "milp": MILPOptimizer,
        "nsga2": NSGA2Optimizer,
        "nsga-ii": NSGA2Optimizer,  # Alias
        "nsga3": NSGA3Optimizer,
        "nsga-iii": NSGA3Optimizer,  # Alias
        "moead": MOEADOptimizer,
        "moea/d": MOEADOptimizer,  # Alias
        "hybrid_milp_moead": HybridMILPMOEADOptimizer,
        "hybrid_milp_nsga3": HybridMILPNSGA3Optimizer,
        "hybrid": HybridMILPMOEADOptimizer,  # Default alias
    }

    @classmethod
    def register_optimizer(cls, name: str, optimizer_class: Type[BaseOptimizer]):
        """Register a new optimizer type"""
        if not issubclass(optimizer_class, BaseOptimizer):
            raise ValueError(f"{optimizer_class} must be a subclass of BaseOptimizer")
        cls._optimizers[name.lower()] = optimizer_class
        logger.info(f"Registered optimizer: {name}")

    @classmethod
    def create_optimizer(cls, algorithm: str, problem_data: Dict[str, Any], config: Dict[str, Any]) -> BaseOptimizer:
        """
        Create an optimizer instance

        Args:
            algorithm: Name of the algorithm to use
            problem_data: Problem-specific data (listings, wishlist, etc.)
            config: Algorithm configuration parameters

        Returns:
            Configured optimizer instance
        """
        algorithm_lower = algorithm.lower()

        if algorithm_lower not in cls._optimizers:
            available = ", ".join(cls._optimizers.keys())
            raise ValueError(f"Unknown algorithm: {algorithm}. Available: {available}")

        optimizer_class = cls._optimizers[algorithm_lower]

        try:
            # Create optimizer instance
            optimizer = optimizer_class(problem_data, config)

            logger.info(
                f"Created {optimizer.get_algorithm_name()} optimizer with config: "
                f"time_limit={config.get('time_limit', 'default')}, "
                f"max_iterations={config.get('max_iterations', 'default')}"
            )

            return optimizer

        except Exception as e:
            logger.error(f"Failed to create {algorithm} optimizer: {str(e)}")
            raise

    @classmethod
    def get_available_algorithms(cls) -> list[str]:
        """Get list of available algorithm names"""
        # Return unique algorithm names (excluding aliases)
        unique_algorithms = []
        seen_classes = set()

        for name, optimizer_class in cls._optimizers.items():
            if optimizer_class not in seen_classes:
                unique_algorithms.append(name)
                seen_classes.add(optimizer_class)

        return sorted(unique_algorithms)

    @classmethod
    def get_algorithm_info(cls, algorithm: str) -> Dict[str, Any]:
        """Get information about a specific algorithm"""
        algorithm_lower = algorithm.lower()

        if algorithm_lower not in cls._optimizers:
            return None

        optimizer_class = cls._optimizers[algorithm_lower]

        # Get algorithm metadata if available
        info = {
            "name": algorithm,
            "class": optimizer_class.__name__,
            "description": optimizer_class.__doc__ or "No description available",
        }

        # Add algorithm-specific parameter info if available
        if hasattr(optimizer_class, "get_parameter_info"):
            info["parameters"] = optimizer_class.get_parameter_info()

        return info

    @classmethod
    def validate_config(cls, algorithm: str, config: Dict[str, Any]) -> bool:
        """Validate configuration for a specific algorithm"""
        algorithm_lower = algorithm.lower()

        if algorithm_lower not in cls._optimizers:
            return False

        optimizer_class = cls._optimizers[algorithm_lower]

        # Use optimizer's validation method if available
        if hasattr(optimizer_class, "validate_config"):
            return optimizer_class.validate_config(config)

        # Default validation - check for required parameters
        required_params = ["time_limit", "max_iterations"]
        return all(param in config for param in required_params)


# Auto-discovery of new optimizers (optional)
def auto_register_optimizers():
    """
    Automatically discover and register optimizer classes.
    This is useful for plugin-based architecture.
    """
    import importlib
    import pkgutil

    # Import all modules in the algorithms package
    import app.optimization.algorithms as algorithms_package

    for importer, modname, ispkg in pkgutil.iter_modules(algorithms_package.__path__):
        if ispkg:
            continue

        try:
            module = importlib.import_module(f"app.optimization.algorithms.{modname}")

            # Look for BaseOptimizer subclasses
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if isinstance(attr, type) and issubclass(attr, BaseOptimizer) and attr is not BaseOptimizer:

                    # Register with a sensible name
                    optimizer_name = attr_name.lower().replace("optimizer", "")
                    OptimizerFactory.register_optimizer(optimizer_name, attr)

        except Exception as e:
            logger.warning(f"Failed to auto-register from {modname}: {e}")