import httpx


async def fetch_yahoo_chart(ticker: str) -> dict:
    """Fetch price/volume data from Yahoo Finance (free, no key needed)."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"interval": "1d", "range": "6mo"}
    headers = {"User-Agent": "TradingJournal/1.0"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()


async def fetch_yahoo_quote(ticker: str) -> dict:
    """Fetch real-time quote summary from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"interval": "1d", "range": "5d"}
    headers = {"User-Agent": "TradingJournal/1.0"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

    result = data["chart"]["result"][0]
    meta = result["meta"]
    indicators = result["indicators"]["quote"][0]

    highs = [h for h in (indicators.get("high") or []) if h is not None]
    lows = [l for l in (indicators.get("low") or []) if l is not None]
    opens = [o for o in (indicators.get("open") or []) if o is not None]
    volumes = [v for v in (indicators.get("volume") or []) if v is not None]

    return {
        "ticker": ticker.upper(),
        "company_name": meta.get("shortName", meta.get("symbol", ticker.upper())),
        "current_price": round(meta.get("regularMarketPrice", 0), 2),
        "previous_close": round(meta.get("chartPreviousClose", meta.get("previousClose", 0)), 2),
        "day_high": round(highs[-1], 2) if highs else 0,
        "day_low": round(lows[-1], 2) if lows else 0,
        "open_price": round(opens[-1], 2) if opens else 0,
        "volume": volumes[-1] if volumes else 0,
        "week_52_high": meta.get("fiftyTwoWeekHigh"),
        "week_52_low": meta.get("fiftyTwoWeekLow"),
    }
