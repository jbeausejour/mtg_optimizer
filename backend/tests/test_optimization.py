import unittest
import pandas as pd
from app.utils.optimization import PurchaseOptimizer

class TestOptimizationEngine(unittest.TestCase):

    def setUp(self):
        # Sample card details
        self.card_details_df = pd.DataFrame({
            'Name': ['Card A', 'Card A', 'Card B', 'Card B', 'Card C'],
            'Site': ['Site 1', 'Site 2', 'Site 1', 'Site 2', 'Site 1'],
            'Quantity': [5, 3, 2, 4, 1],
            'Price': [10, 12, 15, 14, 20],
            'Quality': ['NM', 'LP', 'NM', 'MP', 'NM'],
            'Language': ['English', 'English', 'English', 'English', 'English'],
            'Weighted_Price': [10, 12, 15, 14, 20]
        })

        # Sample buylist
        self.buylist_df = pd.DataFrame({
            'Name': ['Card A', 'Card B', 'Card C'],
            'Quantity': [4, 3, 1]
        })

        # Sample config
        self.config = {
            'min_store': 2,
            'find_min_store': False,
            'milp_strat': True,
            'nsga_algo_strat': False,
            'hybrid_strat': False
        }

        self.optimization_engine = PurchaseOptimizer(self.card_details_df, self.buylist_df, self.config)

    def test_run_milp_optimization(self):
        result, _ = self.optimization_engine.run_milp_optimization()
        if result is None:
            print("MILP optimization did not find a solution")
        else:
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
        self.assertEqual(plan[0]['Name'], 'Card A')
        self.assertEqual(plan[1]['Name'], 'Card B')
        self.assertEqual(plan[2]['Name'], 'Card C')

    def test_milp_with_find_min_store(self):
        self.optimization_engine.config['find_min_store'] = True
        result, all_iterations = self.optimization_engine.run_milp_optimization()
        if result is None:
            print("MILP optimization did not find a solution")
        else:
            self.assertIsNotNone(all_iterations)
            self.assertTrue(len(all_iterations) > 0)

    def test_hybrid_optimization(self):
        # Set up a more complex scenario
        self.card_details_df = pd.DataFrame({
            'Name': ['Card A', 'Card A', 'Card B', 'Card B', 'Card C', 'Card C', 'Card D'],
            'Site': ['Site 1', 'Site 2', 'Site 1', 'Site 3', 'Site 2', 'Site 3', 'Site 1'],
            'Quantity': [5, 3, 2, 4, 3, 2, 1],
            'Price': [10, 12, 15, 14, 20, 18, 25],
            'Quality': ['NM', 'LP', 'NM', 'MP', 'NM', 'LP', 'NM'],
            'Language': ['English'] * 7,
            'Weighted_Price': [10, 15.6, 15, 23.8, 20, 23.4, 25]  # Adjusted for quality
        })

        self.buylist_df = pd.DataFrame({
            'Name': ['Card A', 'Card B', 'Card C', 'Card D'],
            'Quantity': [6, 5, 4, 1]
        })

        self.config['hybrid_strat'] = True
        self.optimization_engine = PurchaseOptimizer(self.card_details_df, self.buylist_df, self.config)

        results = self.optimization_engine.run_optimization()

        if results is None:
            print("Hybrid optimization did not find a solution")
            return

        self.assertIn('sites_results', results)
        purchasing_plan = results['sites_results']

        self.assertTrue(len(purchasing_plan) > 0)

        # Check if the plan satisfies the buylist requirements
        purchased_quantities = {card['Name']: card['Quantity'] for card in purchasing_plan}
        for _, row in self.buylist_df.iterrows():
            self.assertGreaterEqual(purchased_quantities.get(row['Name'], 0), row['Quantity'],
                                    f"Not enough {row['Name']} purchased")

        # Check if the plan uses at least 2 different stores
        used_stores = set(card['Site'] for card in purchasing_plan)
        self.assertGreaterEqual(len(used_stores), 2, "The plan should use at least 2 different stores")

        # Check if the total cost is within a reasonable range
        total_cost = sum(card['Price'] * card['Quantity'] for card in purchasing_plan)
        min_possible_cost = sum(self.card_details_df.groupby('Name')['Price'].min() * self.buylist_df['Quantity'])
        max_possible_cost = sum(self.card_details_df.groupby('Name')['Price'].max() * self.buylist_df['Quantity'])
        self.assertTrue(min_possible_cost <= total_cost <= max_possible_cost,
                        f"Total cost {total_cost} is not within the expected range")

        # Print out the purchasing plan for debugging
        print("Hybrid Optimization Purchasing Plan:")
        for card in purchasing_plan:
            print(f"Buy {card['Quantity']} of {card['Name']} from {card['Site']} at ${card['Price']} each")
        print(f"Total Cost: ${total_cost}")

if __name__ == '__main__':
    unittest.main()