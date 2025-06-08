# backend/tests/test_new_optimization.py
import pytest
from app.optimization.algorithms.factory import OptimizerFactory
from app.optimization.config.algorithm_configs import AlgorithmConfig


class TestNewArchitecture:

    def test_algorithm_factory(self):
        """Test algorithm factory"""
        factory = OptimizerFactory()
        algorithms = factory.get_available_algorithms()
        assert "milp" in algorithms
        assert "moead" in algorithms

    # def test_config_conversion(self):
    #     """Test config conversion from old to new format"""
    #     # Create mock old config
    #     old_config = MockOptimizationConfig()

    #     # Convert to new format
    #     new_config = AlgorithmConfig.from_optimization_config(old_config)

    #     assert new_config.primary_algorithm in ["milp", "moead", "hybrid_milp_moead", "auto"]

    def test_backward_compatibility(self):
        """Test that old code still works"""
        # Test with USE_NEW_ARCHITECTURE = False
        # Test with USE_NEW_ARCHITECTURE = True
        pass
