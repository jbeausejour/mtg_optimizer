# backend/app/optimization/__init__.py
"""
MTG Card Optimization Module

This module provides a flexible framework for optimizing MTG card purchases
using various algorithms including MILP, NSGA-II, MOEA/D, and hybrid approaches.
"""

from .algorithms.factory import OptimizerFactory
from .config.algorithm_configs import AlgorithmConfig

__all__ = ["OptimizerFactory", "AlgorithmConfig"]
