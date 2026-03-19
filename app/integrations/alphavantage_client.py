import httpx
from app.config.settings import settings

BASE_URL = "https://www.alphavantage.co/query"


async def get_global_quote(ticker: str) -> dict:
    """Get real-time price + extended hours data from Alpha Vantage."""
    if not settings.ALPHA_VANTAGE_KEY:
        return {}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            BASE_URL,
            params={
                "function": "GLOBAL_QUOTE",
                "symbol": ticker,
                "apikey": settings.ALPHA_VANTAGE_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    return data.get("Global Quote", {})


async def get_company_overview(ticker: str) -> dict:
    """Get fundamental company data from Alpha Vantage."""
    if not settings.ALPHA_VANTAGE_KEY:
        return {}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            BASE_URL,
            params={
                "function": "OVERVIEW",
                "symbol": ticker,
                "apikey": settings.ALPHA_VANTAGE_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


async def get_earnings(ticker: str) -> dict:
    """Get earnings data from Alpha Vantage."""
    if not settings.ALPHA_VANTAGE_KEY:
        return {}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            BASE_URL,
            params={
                "function": "EARNINGS",
                "symbol": ticker,
                "apikey": settings.ALPHA_VANTAGE_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
