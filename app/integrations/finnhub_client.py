import httpx
from app.config.settings import settings

BASE_URL = "https://finnhub.io/api/v1"


def _headers():
    return {"X-Finnhub-Token": settings.FINNHUB_API_KEY}


async def get_company_profile(ticker: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/stock/profile2",
            params={"symbol": ticker},
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


async def get_basic_financials(ticker: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/stock/metric",
            params={"symbol": ticker, "metric": "all"},
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


async def get_recommendation_trends(ticker: str) -> list:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/stock/recommendation",
            params={"symbol": ticker},
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


async def get_company_news(ticker: str, from_date: str, to_date: str) -> list:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/company-news",
            params={"symbol": ticker, "from": from_date, "to": to_date},
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


async def get_quote(ticker: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/quote",
            params={"symbol": ticker},
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


async def get_price_target(ticker: str) -> dict:
    """Get analyst price target consensus (high, low, mean, median)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/stock/price-target",
            params={"symbol": ticker},
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


async def get_upgrade_downgrade(ticker: str) -> list:
    """Get recent analyst upgrades/downgrades with firm names and ratings."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/stock/upgrade-downgrade",
            params={"symbol": ticker},
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


async def get_earnings_surprises(ticker: str) -> list:
    """Get last 4 quarters of earnings surprises."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/stock/earnings",
            params={"symbol": ticker},
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
