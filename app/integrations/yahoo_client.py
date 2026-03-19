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
    """Fetch real-time quote with regular + pre/post market prices."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"interval": "1d", "range": "5d", "includePrePost": "true"}
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

    regular_price = meta.get("regularMarketPrice", 0)
    previous_close = meta.get("chartPreviousClose", meta.get("previousClose", 0))

    # Post-market data
    post_market_price = meta.get("postMarketPrice")
    post_market_change = meta.get("postMarketChange")
    post_market_change_pct = meta.get("postMarketChangePercent")
    post_market_time = meta.get("postMarketTime")

    # Pre-market data
    pre_market_price = meta.get("preMarketPrice")
    pre_market_change = meta.get("preMarketChange")
    pre_market_change_pct = meta.get("preMarketChangePercent")
    pre_market_time = meta.get("preMarketTime")

    return {
        "ticker": ticker.upper(),
        "company_name": meta.get("shortName", meta.get("symbol", ticker.upper())),
        "current_price": round(regular_price, 2),
        "previous_close": round(previous_close, 2),
        "day_high": round(highs[-1], 2) if highs else 0,
        "day_low": round(lows[-1], 2) if lows else 0,
        "open_price": round(opens[-1], 2) if opens else 0,
        "volume": volumes[-1] if volumes else 0,
        "week_52_high": meta.get("fiftyTwoWeekHigh"),
        "week_52_low": meta.get("fiftyTwoWeekLow"),
        # Extended hours
        "post_market_price": round(post_market_price, 2) if post_market_price else None,
        "post_market_change": round(post_market_change, 2) if post_market_change else None,
        "post_market_change_percent": round(post_market_change_pct, 2) if post_market_change_pct else None,
        "post_market_time": post_market_time,
        "pre_market_price": round(pre_market_price, 2) if pre_market_price else None,
        "pre_market_change": round(pre_market_change, 2) if pre_market_change else None,
        "pre_market_change_percent": round(pre_market_change_pct, 2) if pre_market_change_pct else None,
        "pre_market_time": pre_market_time,
    }
