# backend/app/optimization/preprocessing/penalty_calculator.py
# Move your existing _compute_penalized_price and related methods here
# Add caching as shown in previous artifacts

from functools import lru_cache
import hashlib
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class EnhancedPenaltyCalculator:
    """Enhanced penalty calculator with caching"""

    def __init__(self):
        self._cache = {}
        self._quality_weights = self._precompute_quality_weights()
        self._language_weights = self._precompute_language_weights()

    # Move your existing penalty calculation methods here
    # Add caching decorators
    # Improve performance
