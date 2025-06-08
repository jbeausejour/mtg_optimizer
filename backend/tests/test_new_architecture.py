import asyncio
import pandas as pd
from app.optimization.algorithms.factory import OptimizerFactory
from app.optimization.config.algorithm_configs import AlgorithmConfig


async def test_new_architecture():
    """Test the new optimization architecture"""

    # Create sample data
    sample_listings = pd.DataFrame(
        {
            "name": ["Lightning Bolt", "Lightning Bolt", "Counterspell"],
            "site_name": ["Store A", "Store B", "Store A"],
            "price": [1.0, 1.5, 2.0],
            "quality": ["NM", "LP", "NM"],
            "quantity": [4, 2, 3],
            "site_id": [1, 2, 1],
            "set_name": ["Alpha", "Beta", "Alpha"],
            "set_code": ["LEA", "LEB", "LEA"],
            "language": ["English", "English", "English"],
            "version": ["Standard", "Standard", "Standard"],
            "foil": [False, False, False],
            "variant_id": [1, 2, 3],
        }
    )

    sample_wishlist = pd.DataFrame(
        {"name": ["Lightning Bolt", "Counterspell"], "quantity": [2, 1], "min_quality": ["NM", "LP"]}
    )

    # Create configuration
    config = AlgorithmConfig(
        primary_algorithm="milp", population_size=50, max_generations=10  # Start with MILP for testing
    )

    # Prepare problem data
    problem_data = {
        "filtered_listings_df": sample_listings,
        "user_wishlist_df": sample_wishlist,
        "num_stores": sample_listings["site_name"].nunique(),
    }

    # Test factory
    factory = OptimizerFactory()
    print(f"Available algorithms: {factory.get_available_algorithms()}")

    # Create optimizer
    optimizer = factory.create_optimizer("milp", problem_data, config.to_dict())
    print(f"Created optimizer: {optimizer.get_algorithm_name()}")

    # Run optimization
    result = optimizer.optimize()
    print(f"Optimization completed:")
    print(f"  Algorithm: {result.algorithm_used}")
    print(f"  Execution time: {result.execution_time:.2f}s")
    print(f"  Solutions found: {len(result.all_solutions)}")

    return result


if __name__ == "__main__":
    asyncio.run(test_new_architecture())
