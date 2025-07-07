# backend/app/optimization/debug/diagnostic_wrapper.py
import logging
import traceback
import time
from typing import Dict, Any, Optional, List
import pandas as pd
from collections import defaultdict

logger = logging.getLogger(__name__)


class OptimizationDiagnostics:
    """Comprehensive diagnostics for optimization failures"""

    @staticmethod
    def diagnose_optimization_failure(
        problem_data: Dict, config: Dict, optimizer_class, algorithm_name: str
    ) -> Dict[str, Any]:
        """
        Comprehensive diagnosis of optimization failures

        Returns:
            Dictionary with diagnosis results and recommendations
        """
        diagnosis = {
            "algorithm": algorithm_name,
            "status": "analyzing",
            "issues": [],
            "recommendations": [],
            "data_summary": {},
            "config_issues": [],
            "execution_log": [],
        }

        # 1. Data validation and summary
        data_issues = OptimizationDiagnostics._validate_problem_data(problem_data)
        diagnosis["data_summary"] = data_issues["summary"]
        diagnosis["issues"].extend(data_issues["issues"])

        # 2. Configuration validation
        config_issues = OptimizationDiagnostics._validate_config(config, algorithm_name)
        diagnosis["config_issues"] = config_issues

        # 3. Try to create optimizer and identify specific issues
        creation_result = OptimizationDiagnostics._test_optimizer_creation(optimizer_class, problem_data, config)
        diagnosis["execution_log"].append(creation_result)

        # 4. Test small-scale optimization
        if creation_result["success"]:
            small_test = OptimizationDiagnostics._test_small_optimization(creation_result["optimizer"])
            diagnosis["execution_log"].append(small_test)

        # 5. Generate recommendations
        diagnosis["recommendations"] = OptimizationDiagnostics._generate_recommendations(diagnosis)

        diagnosis["status"] = "completed"
        return diagnosis

    @staticmethod
    def _validate_problem_data(problem_data: Dict) -> Dict[str, Any]:
        """Validate and summarize problem data"""
        issues = []
        summary = {}

        try:
            filtered_df = problem_data.get("filtered_listings_df")
            user_wishlist_df = problem_data.get("user_wishlist_df")

            if filtered_df is None:
                issues.append("filtered_listings_df is None")
                return {"issues": issues, "summary": summary}

            if user_wishlist_df is None:
                issues.append("user_wishlist_df is None")
                return {"issues": issues, "summary": summary}

            # Basic statistics
            summary["num_listings"] = len(filtered_df)
            summary["num_cards_wanted"] = len(user_wishlist_df)
            summary["total_quantity"] = user_wishlist_df["quantity"].sum()
            summary["unique_stores"] = filtered_df["site_name"].nunique()
            summary["unique_cards"] = filtered_df["name"].nunique()

            # Data quality checks
            if len(filtered_df) == 0:
                issues.append("No listings available")

            if len(user_wishlist_df) == 0:
                issues.append("No cards in wishlist")

            # Check for missing critical columns
            required_listing_columns = ["name", "site_name", "price", "quality"]
            missing_cols = [col for col in required_listing_columns if col not in filtered_df.columns]
            if missing_cols:
                issues.append(f"Missing listing columns: {missing_cols}")

            required_wishlist_columns = ["name", "quantity"]
            missing_wish_cols = [col for col in required_wishlist_columns if col not in user_wishlist_df.columns]
            if missing_wish_cols:
                issues.append(f"Missing wishlist columns: {missing_wish_cols}")

            # Check price data
            if "price" in filtered_df.columns:
                price_stats = {
                    "min_price": float(filtered_df["price"].min()),
                    "max_price": float(filtered_df["price"].max()),
                    "avg_price": float(filtered_df["price"].mean()),
                    "null_prices": int(filtered_df["price"].isnull().sum()),
                }
                summary["price_stats"] = price_stats

                if price_stats["null_prices"] > 0:
                    issues.append(f"{price_stats['null_prices']} listings have null prices")

                if price_stats["min_price"] <= 0:
                    issues.append("Some listings have zero or negative prices")

            # Check card coverage
            wanted_cards = set(user_wishlist_df["name"].unique())
            available_cards = set(filtered_df["name"].unique())
            missing_cards = wanted_cards - available_cards

            summary["card_coverage"] = {
                "wanted_cards": len(wanted_cards),
                "available_cards": len(available_cards),
                "missing_cards": len(missing_cards),
                "coverage_rate": len(available_cards & wanted_cards) / len(wanted_cards) if wanted_cards else 0,
            }

            if missing_cards:
                issues.append(f"Missing cards: {list(missing_cards)[:5]}{'...' if len(missing_cards) > 5 else ''}")

            # Store distribution analysis
            store_counts = filtered_df["site_name"].value_counts()
            summary["store_distribution"] = {
                "stores_with_1_card": int((store_counts == 1).sum()),
                "stores_with_5plus_cards": int((store_counts >= 5).sum()),
                "largest_store_inventory": int(store_counts.max()) if len(store_counts) > 0 else 0,
            }

        except Exception as e:
            issues.append(f"Error analyzing problem data: {str(e)}")

        return {"issues": issues, "summary": summary}

    @staticmethod
    def _validate_config(config: Dict, algorithm_name: str) -> List[str]:
        """Validate configuration for specific algorithm"""
        issues = []

        try:
            # Basic validation
            if "weights" not in config:
                issues.append("Missing 'weights' in configuration")
            elif not isinstance(config["weights"], dict):
                issues.append("'weights' must be a dictionary")

            if "min_store" not in config:
                issues.append("Missing 'min_store' in configuration")
            elif config.get("min_store", 0) < 1:
                issues.append("'min_store' must be at least 1")

            if "max_store" not in config:
                issues.append("Missing 'max_store' in configuration")
            elif config.get("max_store", 0) < config.get("min_store", 1):
                issues.append("'max_store' must be >= 'min_store'")

            # Algorithm-specific validation
            if algorithm_name.lower() in ["nsga2", "moead"]:
                if "population_size" not in config:
                    issues.append("Missing 'population_size' for evolutionary algorithm")
                elif config.get("population_size", 0) < 10:
                    issues.append("'population_size' should be at least 10")

                if "max_generations" not in config:
                    issues.append("Missing 'max_generations' for evolutionary algorithm")
                elif config.get("max_generations", 0) < 1:
                    issues.append("'max_generations' must be positive")

        except Exception as e:
            issues.append(f"Error validating config: {str(e)}")

        return issues

    @staticmethod
    def _test_optimizer_creation(optimizer_class, problem_data: Dict, config: Dict) -> Dict[str, Any]:
        """Test if optimizer can be created successfully"""
        result = {"step": "optimizer_creation", "success": False, "error": None, "optimizer": None, "duration": 0}

        start_time = time.time()

        try:
            optimizer = optimizer_class(problem_data, config)
            result["optimizer"] = optimizer
            result["success"] = True
            result["message"] = "Optimizer created successfully"

        except Exception as e:
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            result["message"] = f"Failed to create optimizer: {str(e)}"

        result["duration"] = time.time() - start_time
        return result

    @staticmethod
    def _test_small_optimization(optimizer) -> Dict[str, Any]:
        """Test optimization with minimal problem"""
        result = {"step": "small_optimization_test", "success": False, "error": None, "duration": 0}

        start_time = time.time()

        try:
            # Create minimal test data
            test_listings = pd.DataFrame(
                {
                    "name": ["Test Card"] * 3,
                    "site_name": ["Store A", "Store B", "Store C"],
                    "price": [1.0, 1.5, 2.0],
                    "quality": ["NM", "NM", "LP"],
                    "language": ["English"] * 3,
                    "version": ["Standard"] * 3,
                    "foil": [False] * 3,
                    "set_name": ["Test Set"] * 3,
                    "quantity": [1] * 3,
                }
            )

            test_wishlist = pd.DataFrame(
                {
                    "name": ["Test Card"],
                    "quantity": [1],
                    "quality": ["NM"],
                    "language": ["English"],
                    "version": ["Standard"],
                }
            )

            # Update optimizer data
            optimizer.filtered_listings_df = test_listings
            optimizer.user_wishlist_df = test_wishlist

            # Try to run optimization
            optimization_result = optimizer.optimize()

            if optimization_result and hasattr(optimization_result, "best_solution"):
                result["success"] = True
                result["message"] = "Small optimization test passed"
                result["solution_found"] = bool(optimization_result.best_solution)
            else:
                result["message"] = "Optimization returned no result"

        except Exception as e:
            result["error"] = str(e)
            result["traceback"] = traceback.format_exc()
            result["message"] = f"Small optimization failed: {str(e)}"

        result["duration"] = time.time() - start_time
        return result

    @staticmethod
    def _generate_recommendations(diagnosis: Dict) -> List[str]:
        """Generate actionable recommendations based on diagnosis"""
        recommendations = []

        # Data-based recommendations
        summary = diagnosis.get("data_summary", {})

        if summary.get("num_listings", 0) == 0:
            recommendations.append("No listings available - check data fetching and filtering")

        if summary.get("card_coverage", {}).get("coverage_rate", 0) < 0.5:
            recommendations.append("Low card coverage - consider expanding store selection or relaxing filters")

        if summary.get("num_listings", 0) > 10000:
            recommendations.append("Large dataset - consider using NSGA-II instead of MILP for better performance")

        # Configuration recommendations
        config_issues = diagnosis.get("config_issues", [])
        if config_issues:
            recommendations.append("Fix configuration issues: " + "; ".join(config_issues[:3]))

        # Algorithm-specific recommendations
        algorithm = diagnosis.get("algorithm", "").lower()
        if algorithm in ["nsga2", "moead"]:
            if summary.get("num_listings", 0) < 100:
                recommendations.append("Small problem size - consider using MILP for exact solution")

            recommendations.append(
                "For evolutionary algorithms: try reducing population_size or max_generations if optimization times out"
            )

        # Execution-based recommendations
        execution_log = diagnosis.get("execution_log", [])
        for log_entry in execution_log:
            if not log_entry.get("success", False):
                if "missing dependency" in log_entry.get("error", "").lower():
                    recommendations.append("Install missing dependencies: pip install deap numpy")
                elif "memory" in log_entry.get("error", "").lower():
                    recommendations.append("Reduce problem size or use a different algorithm")
                elif "timeout" in log_entry.get("error", "").lower():
                    recommendations.append("Increase time limit or reduce problem complexity")

        if not recommendations:
            recommendations.append(
                "Try switching to a different optimization algorithm (e.g., MILP if using evolutionary, or NSGA-II if using MILP)"
            )
            recommendations.append("Enable debug logging to get more detailed error information")

        return recommendations


def create_fallback_optimizer_result(algorithm_name: str, error_msg: str) -> Dict[str, Any]:
    """Create a safe fallback result when optimization completely fails"""
    return {
        "status": "Failed",
        "message": f"{algorithm_name} optimization failed: {error_msg}",
        "buylist_id": None,
        "user_id": None,
        "sites_scraped": 0,
        "cards_scraped": 0,
        "solutions": [],
        "errors": {
            "unreachable_stores": [],
            "unknown_languages": [],
            "unknown_qualities": [],
            "optimization_error": error_msg,
        },
        "progress": 100,
        "algorithm_used": algorithm_name,
        "architecture": "Standard",
        "execution_time": 0.0,
        "iterations": 0,
        "convergence_metric": 1.0,
        "performance_stats": {"error": error_msg},
        "algorithm_comparison": None,
        "diagnosis": "Run OptimizationDiagnostics.diagnose_optimization_failure() for detailed analysis",
    }


def safe_optimize_with_diagnostics(optimizer_class, problem_data: Dict, config: Dict, algorithm_name: str):
    """
    Safe optimization wrapper with comprehensive diagnostics

    This function attempts optimization and provides detailed diagnostics on failure
    """
    try:
        # First try normal optimization
        optimizer = optimizer_class(problem_data, config)
        result = optimizer.optimize()

        if result and hasattr(result, "best_solution") and result.best_solution:
            # Success case
            return {
                "status": "Completed",
                "algorithm_used": algorithm_name,
                "best_solution": result.best_solution,
                "all_solutions": getattr(result, "all_solutions", []),
                "execution_time": getattr(result, "execution_time", 0),
                "iterations": getattr(result, "iterations", 0),
            }
        else:
            # No results produced - run diagnostics
            logger.warning(f"{algorithm_name} produced no results - running diagnostics")
            diagnosis = OptimizationDiagnostics.diagnose_optimization_failure(
                problem_data, config, optimizer_class, algorithm_name
            )

            # Create detailed failure result
            failure_result = create_fallback_optimizer_result(
                algorithm_name, "Optimization completed but produced no valid solutions"
            )
            failure_result["diagnosis"] = diagnosis

            return failure_result

    except Exception as e:
        # Complete failure - run diagnostics
        logger.error(f"{algorithm_name} optimization failed with exception: {str(e)}")

        try:
            diagnosis = OptimizationDiagnostics.diagnose_optimization_failure(
                problem_data, config, optimizer_class, algorithm_name
            )
        except Exception as diag_error:
            logger.error(f"Diagnostics also failed: {str(diag_error)}")
            diagnosis = {"error": f"Diagnostics failed: {str(diag_error)}", "original_error": str(e)}

        failure_result = create_fallback_optimizer_result(algorithm_name, str(e))
        failure_result["diagnosis"] = diagnosis

        return failure_result
