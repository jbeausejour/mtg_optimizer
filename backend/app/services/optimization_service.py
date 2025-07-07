import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.dto.optimization_dto import OptimizationResultDTO
from app.models.optimization_results import OptimizationResult
from app.models.scan import Scan
from app.models.buylist import UserBuylist
from app.services.async_base_service import AsyncBaseService

logger = logging.getLogger(__name__)


class OptimizationService(AsyncBaseService[OptimizationResult]):
    """Async service for optimization operations"""

    model_class = OptimizationResult

    @classmethod
    async def create_optimization_result(
        cls, session: AsyncSession, scan_id: int, result_dto: OptimizationResultDTO
    ) -> OptimizationResult:
        """
        Create a new optimization result
        """
        try:
            # Fetch scan asynchronously
            scan_result = await session.execute(select(Scan).where(Scan.id == scan_id))
            scan = scan_result.scalars().first()

            if not scan:
                raise ValueError(f"No scan found with id {scan_id}")
            # Create optimization result
            new_result = await cls.create(
                session,
                **{
                    "scan_id": scan_id,
                    "status": result_dto.status,
                    "message": result_dto.message,
                    "sites_scraped": result_dto.sites_scraped,
                    "cards_scraped": result_dto.cards_scraped,
                    "solutions": [solution.model_dump() for solution in result_dto.solutions],
                    "errors": result_dto.errors,
                    "algorithm_used": result_dto.algorithm_used,
                    "execution_time": result_dto.execution_time,
                    "performance_stats": result_dto.performance_stats,
                },
            )
            return new_result

        except Exception as e:
            logger.error(f"Failed to create optimization result: {str(e)}")
            raise

    @classmethod
    async def get_optimization_results(cls, session: AsyncSession) -> List[OptimizationResult]:
        """Get recent optimization results with related scan and buylist data"""
        try:
            stmt = (
                select(OptimizationResult, Scan, UserBuylist)
                .join(Scan, OptimizationResult.scan_id == Scan.id)
                .outerjoin(UserBuylist, Scan.buylist_id == UserBuylist.id)
                .order_by(OptimizationResult.created_at.desc())
            )

            result = await session.execute(stmt)
            return result.all()
        except Exception as e:
            logger.error(f"Error fetching optimization results: {str(e)}")
            return []

    @classmethod
    async def get_optimization_results_enhanced(
        cls,
        session: AsyncSession,
        limit: Optional[int] = None,
        algorithm_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get optimization results with enhanced data and filtering
        """
        try:
            # Build query using proper async SQLAlchemy patterns
            stmt = (
                select(OptimizationResult)
                .options(selectinload(OptimizationResult.scan))
                .order_by(desc(OptimizationResult.created_at))
            )

            # Apply filters if provided
            if algorithm_filter:
                stmt = stmt.where(OptimizationResult.algorithm_used == algorithm_filter)

            if status_filter:
                stmt = stmt.where(OptimizationResult.status == status_filter)

            # Apply limit if provided
            if limit:
                stmt = stmt.limit(limit)

            # Execute query
            result = await session.execute(stmt)
            optimization_results = result.scalars().all()

            # Convert to enhanced dictionaries
            enhanced_results = []
            for opt_result in optimization_results:
                try:
                    # Get buylist name from scan if available
                    buylist_name = None
                    if opt_result.scan and hasattr(opt_result.scan, "buylist_id"):
                        # You might need to fetch buylist data here or add to the query
                        buylist_name = f"Buylist {opt_result.scan.buylist_id}"

                    # Use the enhanced to_dict method (if available) or regular to_dict
                    if hasattr(opt_result, "to_dict_enhanced"):
                        result_dict = opt_result.to_dict_enhanced()
                    else:
                        # Use regular to_dict but ensure all fields are included
                        result_dict = opt_result.to_dict()

                        # Ensure the new fields are included (in case to_dict wasn't updated)
                        if "algorithm_used" not in result_dict:
                            result_dict["algorithm_used"] = opt_result.algorithm_used
                        if "execution_time" not in result_dict:
                            result_dict["execution_time"] = opt_result.execution_time
                        if "performance_stats" not in result_dict:
                            result_dict["performance_stats"] = opt_result.performance_stats

                    # Add additional computed fields
                    result_dict["buylist_name"] = buylist_name

                    # Add performance insights if available
                    if opt_result.execution_time and opt_result.algorithm_used:
                        result_dict["performance_insights"] = cls.generate_performance_insights(opt_result)

                    enhanced_results.append(result_dict)

                except Exception as e:
                    logger.warning(f"Error processing optimization result {opt_result.id}: {str(e)}")
                    # Add basic result even if enhancement fails
                    try:
                        basic_result = opt_result.to_dict()
                        basic_result["buylist_name"] = buylist_name
                        enhanced_results.append(basic_result)
                    except Exception as e2:
                        logger.error(f"Failed to process result {opt_result.id}: {str(e2)}")
                        continue

            return enhanced_results

        except Exception as e:
            logger.error(f"Error fetching enhanced optimization results: {str(e)}")
            return []

    @classmethod
    async def get_optimization_results_simple(
        cls, session: AsyncSession, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get optimization results with manual field enhancement
        """
        try:
            stmt = select(OptimizationResult).order_by(desc(OptimizationResult.created_at))

            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            optimization_results = result.scalars().all()

            # Convert to dictionaries and ensure all fields are included
            results_data = []
            for opt_result in optimization_results:
                try:
                    result_dict = opt_result.to_dict()  # Original method

                    # Manually add the missing fields if they're not in to_dict
                    if "algorithm_used" not in result_dict:
                        result_dict["algorithm_used"] = opt_result.algorithm_used
                    if "execution_time" not in result_dict:
                        result_dict["execution_time"] = opt_result.execution_time
                    if "performance_stats" not in result_dict:
                        result_dict["performance_stats"] = opt_result.performance_stats

                    # Add computed performance score if available
                    if opt_result.execution_time and opt_result.solutions:
                        try:
                            # Calculate a simple performance score
                            solutions = opt_result.solutions if isinstance(opt_result.solutions, list) else []
                            best_solution = next((s for s in solutions if s.get("is_best_solution")), None)

                            if best_solution:
                                completion_rate = (
                                    best_solution.get("nbr_card_in_solution", 0)
                                    / max(best_solution.get("cards_required_total", 1), 1)
                                ) * 100
                                time_score = max(0, 100 - (opt_result.execution_time / 3))
                                performance_score = round((time_score + completion_rate) / 2)
                                result_dict["performance_score"] = performance_score
                        except Exception as e:
                            logger.warning(f"Error calculating performance score: {str(e)}")

                    results_data.append(result_dict)

                except Exception as e:
                    logger.warning(f"Error processing result {opt_result.id}: {str(e)}")
                    continue

            return results_data

        except Exception as e:
            logger.error(f"Error fetching simple optimization results: {str(e)}")
            return []

    @classmethod
    async def get_optimization_analytics(cls, session: AsyncSession) -> Dict[str, Any]:
        """
        Get aggregated performance analytics across all optimizations
        """
        try:
            # Get all completed optimizations using proper async SQLAlchemy
            stmt = (
                select(OptimizationResult)
                .where(OptimizationResult.status == "Completed")
                .where(OptimizationResult.execution_time.isnot(None))
                .options(selectinload(OptimizationResult.scan))
            )

            result = await session.execute(stmt)
            results = result.scalars().all()

            if not results:
                return {
                    "avg_execution_time": 0,
                    "success_rate": 0,
                    "most_used_algorithm": "None",
                    "avg_solution_quality": 0,
                    "algorithm_comparison": {},
                }

            # Calculate analytics
            total_results = len(results)
            successful_results = [r for r in results if r.status == "Completed"]

            # Average execution time
            execution_times = [r.execution_time for r in results if r.execution_time]
            avg_execution_time = sum(execution_times) / len(execution_times) if execution_times else 0

            # Success rate
            success_rate = (len(successful_results) / total_results) * 100 if total_results > 0 else 0

            # Most used algorithm
            algorithm_counts = {}
            for result in results:
                algo = result.algorithm_used or "Unknown"
                algorithm_counts[algo] = algorithm_counts.get(algo, 0) + 1

            most_used_algorithm = max(algorithm_counts.items(), key=lambda x: x[1])[0] if algorithm_counts else "None"

            # Average solution quality
            solution_qualities = []
            for result in results:
                try:
                    if result.solutions:
                        # Handle both list of dicts and already parsed solutions
                        solutions = result.solutions if isinstance(result.solutions, list) else []
                        best_solution = next((s for s in solutions if s.get("is_best_solution")), None)

                        if best_solution and best_solution.get("cards_required_total", 0) > 0:
                            quality = (
                                best_solution.get("nbr_card_in_solution", 0)
                                / best_solution.get("cards_required_total", 1)
                            ) * 100
                            solution_qualities.append(quality)
                except Exception as e:
                    logger.warning(f"Error calculating solution quality for result {result.id}: {str(e)}")
                    continue

            avg_solution_quality = sum(solution_qualities) / len(solution_qualities) if solution_qualities else 0

            # Algorithm comparison
            algorithm_comparison = {}
            for algo in algorithm_counts.keys():
                algo_results = [r for r in results if r.algorithm_used == algo]
                algo_exec_times = [r.execution_time for r in algo_results if r.execution_time]
                algo_successful = [r for r in algo_results if r.status == "Completed"]

                algorithm_comparison[algo] = {
                    "usage_count": len(algo_results),
                    "avg_time": sum(algo_exec_times) / len(algo_exec_times) if algo_exec_times else 0,
                    "success_rate": (len(algo_successful) / len(algo_results)) * 100 if algo_results else 0,
                }

            analytics = {
                "avg_execution_time": round(avg_execution_time, 2),
                "success_rate": round(success_rate, 1),
                "most_used_algorithm": most_used_algorithm,
                "avg_solution_quality": round(avg_solution_quality, 1),
                "algorithm_comparison": algorithm_comparison,
                "total_optimizations": total_results,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            return analytics

        except Exception as e:
            logger.error(f"Error generating analytics: {str(e)}")
            return {
                "avg_execution_time": 0,
                "success_rate": 0,
                "most_used_algorithm": "None",
                "avg_solution_quality": 0,
                "algorithm_comparison": {},
                "error": str(e),
            }

    @classmethod
    def generate_performance_insights(cls, result: OptimizationResult) -> List[str]:
        """
        Generate performance insights for a single optimization result
        """
        insights = []

        try:
            # Execution time insights
            if result.execution_time:
                if result.execution_time < 10:
                    insights.append("Fast execution")
                elif result.execution_time > 60:
                    insights.append("Long execution time")

            # Algorithm-specific insights
            if result.algorithm_used:
                algo = result.algorithm_used.lower()
                if algo == "milp" and result.execution_time and result.execution_time > 30:
                    insights.append("MILP took longer than expected - consider hybrid approach for larger problems")
                elif (
                    algo == "nsga2"
                    and result.performance_stats
                    and result.performance_stats.get("convergence_achieved")
                ):
                    insights.append("NSGA-II achieved good convergence")
                elif algo == "hybrid":
                    insights.append("Hybrid algorithm provides balanced performance")

            # Solution quality insights
            if result.solutions:
                try:
                    solutions = result.solutions if isinstance(result.solutions, list) else []
                    best_solution = next((s for s in solutions if s.get("is_best_solution")), None)

                    if best_solution:
                        completion_rate = (
                            best_solution.get("nbr_card_in_solution", 0)
                            / max(best_solution.get("cards_required_total", 1), 1)
                        ) * 100
                        if completion_rate == 100:
                            insights.append("Perfect solution - all cards found")
                        elif completion_rate > 90:
                            insights.append("Excellent solution quality")
                        elif completion_rate < 70:
                            insights.append("Consider relaxing preferences or adding more sites")
                except Exception as e:
                    logger.warning(f"Error calculating solution insights: {str(e)}")

        except Exception as e:
            logger.warning(f"Error generating performance insights: {str(e)}")

        return insights

    @classmethod
    async def get_optimization_results_by_scan(cls, session: AsyncSession, scan_id: int) -> List[OptimizationResult]:
        """Get optimization results for a specific scan"""
        try:
            result = await session.execute(select(OptimizationResult).filter(OptimizationResult.scan_id == scan_id))
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching results for scan {scan_id}: {str(e)}")
            return []

    @classmethod
    async def get_latest_optimization(cls, session: AsyncSession) -> Optional[OptimizationResult]:
        """Get the most recent optimization result"""
        try:
            result = await session.execute(
                select(OptimizationResult).order_by(OptimizationResult.created_at.desc()).limit(1)
            )
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error fetching latest optimization: {str(e)}")
            return None

    @classmethod
    async def delete_optimization_by_id(cls, session: AsyncSession, id: int) -> bool:
        """Delete optimization result(s) associated with a scan ID"""
        try:
            stmt = select(cls.model_class).where(cls.model_class.id == id)
            results = (await session.execute(stmt)).scalars().all()

            if not results:
                return False

            for result in results:
                await session.delete(result)
            return True

        except Exception as e:
            logger.error(f"Error deleting optimization result for id {id}: {e}")
            return False

    @classmethod
    async def delete_bulk_by_ids(cls, session: AsyncSession, ids: list[int]) -> list[int]:
        """Delete multiple optimization results by scan IDs"""
        try:
            if not ids:
                return []

            # Get all optimization results for the given scan IDs
            stmt = select(cls.model_class).where(cls.model_class.id.in_(ids))
            results = await session.execute(stmt)
            to_delete = results.scalars().all()

            deleted_ids = []
            for result in to_delete:
                deleted_ids.append(result.id)
                await session.delete(result)

            logger.info(f"Successfully deleted {len(deleted_ids)} optimization results")
            return deleted_ids

        except Exception as e:
            logger.error(f"Error deleting optimization results for id {ids}: {e}")
            # Fixed: Return empty list instead of False to match return type annotation
            return []
