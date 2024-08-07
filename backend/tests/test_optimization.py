import unittest
import pandas as pd
from app.utils.optimization import PurchaseOptimizer
import sys

class TestMILPOptimization(unittest.TestCase):

    def setUp(self):
        self.config = {
            'min_store': 2,
            'find_min_store': False,
            'milp_strat': True,
            'nsga_algo_strat': False,
            'hybrid_strat': False
        }
        print(f"\n{'='*80}\nRunning test: {self._testMethodName}\n{'='*80}")

    def create_optimizer(self, card_details, buylist):
        card_details_df = pd.DataFrame(card_details)
        buylist_df = pd.DataFrame(buylist)
        return PurchaseOptimizer(card_details_df, buylist_df, self.config)

    def print_solution(self, result):
        if result is not None:
            print("\nSolution found:")
            print(result.to_string(index=False))
            print(f"\nTotal cost: ${(result['Price'] * result['Quantity']).sum():.2f}")
            print(f"Number of stores used: {result['Site'].nunique()}")
        else:
            print("\nNo solution found.")

    def test_basic_milp_optimization(self):
        card_details = {
            'Name': ['Card A', 'Card A', 'Card B', 'Card B'],
            'Site': ['Site 1', 'Site 2', 'Site 1', 'Site 2'],
            'Quantity': [5, 3, 2, 4],
            'Price': [10, 12, 15, 14],
            'Quality': ['NM', 'LP', 'NM', 'MP'],
            'Language': ['English'] * 4,
            'Weighted_Price': [10, 12, 15, 14]
        }
        buylist = {
            'Name': ['Card A', 'Card B'],
            'Quantity': [4, 3]
        }
        optimizer = self.create_optimizer(card_details, buylist)
        result, _ = optimizer.run_milp_optimization()
        self.print_solution(result)
        self.assertIsNotNone(result, "Basic MILP optimization should find a solution")
        self.assertEqual(len(result), 2, "Should have results for both cards")
        total_quantity = result['Quantity'].sum()
        self.assertEqual(total_quantity, 7, "Total quantity should match buylist")

    def test_milp_with_insufficient_quantity(self):
        card_details = {
            'Name': ['Card A', 'Card B'],
            'Site': ['Site 1', 'Site 1'],
            'Quantity': [2, 2],
            'Price': [10, 15],
            'Quality': ['NM', 'NM'],
            'Language': ['English'] * 2,
            'Weighted_Price': [10, 15]
        }
        buylist = {
            'Name': ['Card A', 'Card B'],
            'Quantity': [3, 3]
        }
        optimizer = self.create_optimizer(card_details, buylist)
        result, _ = optimizer.run_milp_optimization()
        self.print_solution(result)
        self.assertIsNone(result, "Should not find a solution when quantities are insufficient")

    def test_milp_multi_store_requirement(self):
        card_details = {
            'Name': ['Card A', 'Card A', 'Card B', 'Card B'],
            'Site': ['Site 1', 'Site 2', 'Site 1', 'Site 2'],
            'Quantity': [5, 3, 2, 4],
            'Price': [10, 12, 15, 14],
            'Quality': ['NM', 'LP', 'NM', 'MP'],
            'Language': ['English'] * 4,
            'Weighted_Price': [10, 12, 15, 14]
        }
        buylist = {
            'Name': ['Card A', 'Card B'],
            'Quantity': [6, 5]
        }
        self.config['min_store'] = 2
        optimizer = self.create_optimizer(card_details, buylist)
        result, _ = optimizer.run_milp_optimization()
        self.print_solution(result)
        self.assertIsNotNone(result, "Multi-store MILP optimization should find a solution")
        used_stores = result['Site'].nunique()
        self.assertGreaterEqual(used_stores, 2, "Should use at least 2 stores")

    def test_milp_minimize_cost(self):
        card_details = {
            'Name': ['Card A', 'Card A', 'Card B', 'Card B'],
            'Site': ['Site 1', 'Site 2', 'Site 1', 'Site 2'],
            'Quantity': [5, 5, 5, 5],
            'Price': [10, 12, 15, 13],
            'Quality': ['NM', 'NM', 'NM', 'NM'],
            'Language': ['English'] * 4,
            'Weighted_Price': [10, 12, 15, 13]
        }
        buylist = {
            'Name': ['Card A', 'Card B'],
            'Quantity': [5, 5]
        }
        optimizer = self.create_optimizer(card_details, buylist)
        result, _ = optimizer.run_milp_optimization()
        self.print_solution(result)
        self.assertIsNotNone(result, "Cost minimization MILP should find a solution")
        total_cost = (result['Price'] * result['Quantity']).sum()
        self.assertEqual(total_cost, 115, "Total cost should be minimized")

    def test_milp_with_quality_preference(self):
        card_details = {
            'Name': ['Card A', 'Card A', 'Card A'],
            'Site': ['Site 1', 'Site 2', 'Site 3'],
            'Quantity': [2, 2, 2],
            'Price': [10, 10, 10],
            'Quality': ['NM', 'LP', 'MP'],
            'Language': ['English'] * 3,
            'Weighted_Price': [10, 13, 17]
        }
        buylist = {
            'Name': ['Card A'],
            'Quantity': [4]
        }
        optimizer = self.create_optimizer(card_details, buylist)
        result, _ = optimizer.run_milp_optimization()
        self.print_solution(result)
        self.assertIsNotNone(result, "Quality preference MILP should find a solution")
        self.assertTrue(all(result['Quality'] != 'MP'), "Should prefer higher quality cards")

    def test_milp_with_language_preference(self):
        card_details = {
            'Name': ['Card A', 'Card A'],
            'Site': ['Site 1', 'Site 2'],
            'Quantity': [2, 2],
            'Price': [10, 9],
            'Quality': ['NM', 'NM'],
            'Language': ['English', 'Japanese'],
            'Weighted_Price': [10, 11.7]  # Assuming 30% markup for non-English
        }
        buylist = {
            'Name': ['Card A'],
            'Quantity': [2]
        }
        optimizer = self.create_optimizer(card_details, buylist)
        result, _ = optimizer.run_milp_optimization()
        self.print_solution(result)
        self.assertIsNotNone(result, "Language preference MILP should find a solution")
        self.assertEqual(result.iloc[0]['Language'], 'English', "Should prefer English language")

    def test_milp_with_find_min_store(self):
        card_details = {
            'Name': ['Card A', 'Card A', 'Card B', 'Card B', 'Card C', 'Card C'],
            'Site': ['Site 1', 'Site 2', 'Site 1', 'Site 2', 'Site 1', 'Site 2'],
            'Quantity': [3, 3, 2, 4, 2, 3],
            'Price': [10, 12, 15, 14, 20, 18],
            'Quality': ['NM', 'LP', 'NM', 'MP', 'NM', 'LP'],
            'Language': ['English'] * 6,
            'Weighted_Price': [10, 15.6, 15, 23.8, 20, 23.4]
        }
        buylist = {
            'Name': ['Card A', 'Card B', 'Card C'],
            'Quantity': [5, 5, 4]
        }
        self.config['find_min_store'] = True
        optimizer = self.create_optimizer(card_details, buylist)
        result, all_iterations = optimizer.run_milp_optimization()
        self.print_solution(result)
        print("\nAll iterations:")
        for i, iteration in enumerate(all_iterations, 1):
            print(f"\nIteration {i}:")
            print(f"Number of stores: {iteration['Number_store']}")
            print(f"Total price: ${iteration['Total_price']:.2f}")
            print("Cards purchased:")
            print(iteration['sorted_results_df'][['Name', 'Site', 'Quantity', 'Price']].to_string(index=False))
        
        self.assertIsNotNone(result, "Find min store MILP should find a solution")
        self.assertIsNotNone(all_iterations, "Should return all iterations")
        self.assertGreater(len(all_iterations), 0, "Should have multiple iterations")
        
        # Check if the number of stores decreases with each iteration
        num_stores = [iteration['Number_store'] for iteration in all_iterations]
        self.assertEqual(num_stores, sorted(num_stores, reverse=True), "Number of stores should decrease")

    def test_milp_with_edge_case_single_store(self):
        card_details = {
            'Name': ['Card A', 'Card B', 'Card C'],
            'Site': ['Site 1', 'Site 1', 'Site 1'],
            'Quantity': [5, 5, 5],
            'Price': [10, 15, 20],
            'Quality': ['NM', 'NM', 'NM'],
            'Language': ['English'] * 3,
            'Weighted_Price': [10, 15, 20]
        }
        buylist = {
            'Name': ['Card A', 'Card B', 'Card C'],
            'Quantity': [3, 3, 3]
        }
        self.config['min_store'] = 1
        optimizer = self.create_optimizer(card_details, buylist)
        result, _ = optimizer.run_milp_optimization()
        self.print_solution(result)
        self.assertIsNotNone(result, "Single store MILP should find a solution")
        self.assertEqual(result['Site'].nunique(), 1, "Should use only one store")

    def test_milp_with_high_cost_penalty(self):
        card_details = {
            'Name': ['Card A', 'Card A', 'Card B', 'Card B'],
            'Site': ['Site 1', 'Site 2', 'Site 1', 'Site 2'],
            'Quantity': [5, 5, 5, 5],
            'Price': [10, 10000, 15, 10000],  # High cost for Site 2
            'Quality': ['NM', 'NM', 'NM', 'NM'],
            'Language': ['English'] * 4,
            'Weighted_Price': [10, 10000, 15, 10000]
        }
        buylist = {
            'Name': ['Card A', 'Card B'],
            'Quantity': [5, 5]
        }
        optimizer = self.create_optimizer(card_details, buylist)
        result, _ = optimizer.run_milp_optimization()
        self.print_solution(result)
        self.assertIsNotNone(result, "High cost penalty MILP should find a solution")
        self.assertTrue(all(result['Site'] == 'Site 1'), "Should only use Site 1 due to high cost penalty")

def run_tests_with_output():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMILPOptimization)
    unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)

if __name__ == '__main__':
    run_tests_with_output()