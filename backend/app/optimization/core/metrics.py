# backend/app/optimization/core/metrics.py
import time


class OptimizationMetrics:
    """Track optimization performance and quality"""

    def __init__(self):
        self.metrics = {}

    def record_optimization(self, algorithm, execution_time, solution_quality, problem_size, problem_characteristics):
        """Record optimization metrics"""
        if algorithm not in self.metrics:
            self.metrics[algorithm] = []

        self.metrics[algorithm].append(
            {
                "execution_time": execution_time,
                "solution_quality": solution_quality,
                "problem_size": problem_size,
                "problem_characteristics": problem_characteristics,
                "timestamp": time.time(),
            }
        )

    def get_recent_runs(self, algorithm, limit=5):
        return self.metrics.get(algorithm, [])[-limit:]

    def get_algorithm_performance(self, algorithm):
        """Get performance statistics for algorithm"""
        if algorithm not in self.metrics:
            return None

        data = self.metrics[algorithm]
        return {
            "avg_complexity_score": sum(d["problem_characteristics"].get("complexity_score", 0) for d in data)
            / len(data),
            "avg_num_cards": sum(d["problem_characteristics"].get("num_cards", 0) for d in data) / len(data),
            "avg_num_stores": sum(d["problem_characteristics"].get("num_stores", 0) for d in data) / len(data),
            "avg_execution_time": sum(d["execution_time"] for d in data) / len(data),
            "avg_solution_quality": sum(d["solution_quality"] for d in data) / len(data),
            "total_runs": len(data),
        }

    def export_metrics(self, as_csv=False):
        import pandas as pd

        flat = []
        for algo, entries in self.metrics.items():
            for entry in entries:
                flat.append({"algorithm": algo, **entry})

        df = pd.DataFrame(flat)
        return df.to_csv() if as_csv else df.to_dict(orient="records")
