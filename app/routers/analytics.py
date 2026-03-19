from fastapi import APIRouter
from app.services.analytics import get_performance_stats, get_strategy_breakdown
from app.models.schemas import PerformanceStats, StrategyBreakdown

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


@router.get("/performance", response_model=PerformanceStats)
async def performance():
    """Get overall trading performance statistics.

    Returns win rate, profit factor, expectancy, best/worst trades, etc.
    """
    return get_performance_stats()


@router.get("/strategies", response_model=list[StrategyBreakdown])
async def strategies():
    """Get P&L breakdown by strategy."""
    return get_strategy_breakdown()
