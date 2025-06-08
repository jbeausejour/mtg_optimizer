# backend/app/optimization/core/metrics.py
from datetime import time


class OptimizationMetrics:
    """Track optimization performance and quality"""

    def __init__(self):
        self.metrics = {}

    def record_optimization(self, algorithm, execution_time, solution_quality, problem_size):
        """Record optimization metrics"""
        if algorithm not in self.metrics:
            self.metrics[algorithm] = []

        self.metrics[algorithm].append(
            {
                "execution_time": execution_time,
                "solution_quality": solution_quality,
                "problem_size": problem_size,
                "timestamp": time.time(),
            }
        )

    def get_algorithm_performance(self, algorithm):
        """Get performance statistics for algorithm"""
        if algorithm not in self.metrics:
            return None

        data = self.metrics[algorithm]
        return {
            "avg_execution_time": sum(d["execution_time"] for d in data) / len(data),
            "avg_solution_quality": sum(d["solution_quality"] for d in data) / len(data),
            "total_runs": len(data),
        }
