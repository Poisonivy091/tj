import httpx
from app.config.settings import settings

BASE_URL = "https://newsapi.org/v2"


async def search_news(query: str, page_size: int = 10) -> list[dict]:
    """Search for news articles about a stock via NewsAPI."""
    if not settings.NEWSAPI_KEY:
        return []
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/everything",
            params={
                "q": query,
                "sortBy": "publishedAt",
                "pageSize": page_size,
                "language": "en",
                "apiKey": settings.NEWSAPI_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    return data.get("articles", [])
