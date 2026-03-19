from fastapi import APIRouter, HTTPException
from app.services.research import deep_research
from app.models.schemas import ResearchReport

router = APIRouter(prefix="/api/v1/research", tags=["Research"])


@router.get("/{ticker}", response_model=ResearchReport)
async def research_stock(ticker: str):
    """Run deep research on a stock ticker.

    Returns quote, fundamentals, technicals, news, analyst ratings,
    and a composite score (0-100).
    """
    try:
        report = await deep_research(ticker.upper())
        return report
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Research failed: {e}")
