import unittest

import pandas as pd
from app.utils.optimization import PurchaseOptimizer


class TestOptimizationEngine(unittest.TestCase):

    def setUp(self):
        # Sample card details
        self.card_details_df = pd.DataFrame(
            {
                "Name": ["Card A", "Card A", "Card B", "Card B", "Card C"],
                "Site": ["Site 1", "Site 2", "Site 1", "Site 2", "Site 1"],
                "Quantity": [5, 3, 2, 4, 1],
                "Price": [10, 12, 15, 14, 20],
                "Quality": ["NM", "LP", "NM", "MP", "NM"],
                "Language": ["English", "English", "English", "English", "English"],
                "Weighted_Price": [10, 12, 15, 14, 20],
            }
        )

        # Sample buylist
        self.buylist_df = pd.DataFrame({"Name": ["Card A", "Card B", "Card C"], "Quantity": [4, 3, 1]})

        self.optimization_engine = PurchaseOptimizer(self.card_details_df, self.buylist_df)

    def test_run_milp_optimization(self):
        result, _ = self.optimization_engine.run_milp_optimization(min_store=2, find_min_store=False)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)  # We expect 3 rows in the result (one for each card)

    def test_run_nsga_ii_optimization(self):
        pareto_front = self.optimization_engine.run_nsga_ii_optimization()
        self.assertIsNotNone(pareto_front)
        self.assertTrue(len(pareto_front) > 0)

    def test_get_purchasing_plan(self):
        # Create a mock solution
        mock_solution = [0, 2, 4]  # Indices of rows in card_details_df
        plan = self.optimization_engine.get_purchasing_plan(mock_solution)
        self.assertEqual(len(plan), 3)
        self.assertEqual(plan[0]["Name"], "Card A")
        self.assertEqual(plan[1]["Name"], "Card B")
        self.assertEqual(plan[2]["Name"], "Card C")

    def test_milp_with_find_min_store(self):
        result, all_iterations = self.optimization_engine.run_milp_optimization(min_store=2, find_min_store=True)
        self.assertIsNotNone(result)
        self.assertIsNotNone(all_iterations)
        self.assertTrue(len(all_iterations) > 0)


if __name__ == "__main__":
    unittest.main()
