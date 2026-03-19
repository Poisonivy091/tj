from datetime import datetime, timedelta, timezone

import numpy as np

from app.integrations.yahoo_client import fetch_yahoo_chart, fetch_yahoo_quote
from app.integrations.finnhub_client import (
    get_basic_financials,
    get_company_news,
    get_recommendation_trends,
)
from app.models.schemas import (
    FundamentalData,
    NewsSentiment,
    ResearchReport,
    StockQuote,
    TechnicalData,
)


def _sma(prices: list[float], window: int) -> float | None:
    if len(prices) < window:
        return None
    return round(float(np.mean(prices[-window:])), 2)


def _rsi(prices: list[float], period: int = 14) -> float | None:
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = float(np.mean(gains))
    avg_loss = float(np.mean(losses))
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _atr(highs: list, lows: list, closes: list, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        if h is None or l is None or pc is None:
            continue
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    return round(float(np.mean(trs[-period:])), 2)


def _analyst_consensus(recommendations: list) -> str | None:
    if not recommendations:
        return None
    latest = recommendations[0]
    buy = latest.get("buy", 0) + latest.get("strongBuy", 0)
    hold = latest.get("hold", 0)
    sell = latest.get("sell", 0) + latest.get("strongSell", 0)
    total = buy + hold + sell
    if total == 0:
        return None
    if buy / total > 0.6:
        return f"Strong Buy ({buy}/{total} analysts)"
    elif buy / total > 0.4:
        return f"Buy ({buy}/{total} analysts)"
    elif sell / total > 0.4:
        return f"Sell ({sell}/{total} analysts)"
    return f"Hold ({hold}/{total} analysts)"


def _composite_score(
    fundamentals: FundamentalData,
    technicals: TechnicalData,
    analyst: str | None,
    change_pct: float,
) -> int:
    """Simple 0-100 composite score."""
    score = 50  # neutral baseline

    # Fundamentals
    if fundamentals.pe_ratio and 0 < fundamentals.pe_ratio < 25:
        score += 5
    if fundamentals.roe and fundamentals.roe > 15:
        score += 5
    if fundamentals.debt_equity is not None and fundamentals.debt_equity < 1:
        score += 5
    if fundamentals.revenue_growth and fundamentals.revenue_growth > 0:
        score += 5

    # Technicals
    if technicals.rsi_14:
        if technicals.rsi_14 < 30:
            score += 10  # oversold = opportunity
        elif technicals.rsi_14 > 70:
            score -= 10  # overbought = caution

    if technicals.sma_50 and technicals.sma_200:
        if technicals.sma_50 > technicals.sma_200:
            score += 5  # golden cross territory

    # Analyst
    if analyst and "Strong Buy" in analyst:
        score += 10
    elif analyst and "Buy" in analyst:
        score += 5
    elif analyst and "Sell" in analyst:
        score -= 10

    # Momentum
    if change_pct > 2:
        score += 3
    elif change_pct < -2:
        score -= 3

    return max(0, min(100, score))


async def deep_research(ticker: str) -> ResearchReport:
    """Run comprehensive research on a ticker."""
    ticker = ticker.upper()
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    # Fetch all data concurrently-ish (sequential for simplicity, could use asyncio.gather)
    quote_data = await fetch_yahoo_quote(ticker)
    chart_data = await fetch_yahoo_chart(ticker)

    # Finnhub data (gracefully degrade if no key)
    financials = {}
    recommendations = []
    news_items = []
    try:
        financials = await get_basic_financials(ticker)
    except Exception:
        pass
    try:
        recommendations = await get_recommendation_trends(ticker)
    except Exception:
        pass
    try:
        news_raw = await get_company_news(ticker, month_ago, today)
        news_items = news_raw[:10]  # latest 10
    except Exception:
        pass

    # Parse chart for technicals
    chart_result = chart_data.get("chart", {}).get("result", [{}])[0]
    chart_indicators = chart_result.get("indicators", {}).get("quote", [{}])[0]
    closes = [c for c in (chart_indicators.get("close") or []) if c is not None]
    highs_list = [h for h in (chart_indicators.get("high") or []) if h is not None]
    lows_list = [l for l in (chart_indicators.get("low") or []) if l is not None]

    meta = chart_result.get("meta", {})

    # Build fundamentals
    metric = financials.get("metric", {})
    fundamentals = FundamentalData(
        pe_ratio=metric.get("peNormalizedAnnual"),
        pb_ratio=metric.get("pbAnnual"),
        ps_ratio=metric.get("psAnnual"),
        roe=metric.get("roeTTM"),
        debt_equity=metric.get("totalDebt/totalEquityAnnual"),
        free_cash_flow=metric.get("freeCashFlowTTM"),
        revenue_growth=metric.get("revenueGrowthTTMAnnual"),
        eps_growth=metric.get("epsGrowthTTMAnnual"),
        dividend_yield=metric.get("dividendYieldIndicatedAnnual"),
        market_cap=metric.get("marketCapitalization"),
    )

    # Build technicals
    technicals = TechnicalData(
        sma_20=_sma(closes, 20),
        sma_50=_sma(closes, 50),
        sma_200=_sma(closes, 200) if len(closes) >= 200 else None,
        rsi_14=_rsi(closes),
        week_52_high=meta.get("fiftyTwoWeekHigh") or metric.get("52WeekHigh"),
        week_52_low=meta.get("fiftyTwoWeekLow") or metric.get("52WeekLow"),
        beta=metric.get("beta"),
        atr=_atr(highs_list, lows_list, closes),
    )

    # Build quote
    prev_close = quote_data["previous_close"]
    curr_price = quote_data["current_price"]
    change_pct = round(((curr_price - prev_close) / prev_close * 100) if prev_close else 0, 2)

    quote = StockQuote(
        ticker=ticker,
        company_name=quote_data["company_name"],
        current_price=curr_price,
        change_percent=change_pct,
        day_high=quote_data["day_high"],
        day_low=quote_data["day_low"],
        open_price=quote_data["open_price"],
        previous_close=prev_close,
        volume=quote_data["volume"],
    )

    # Build news
    news = [
        NewsSentiment(
            headline=n.get("headline", ""),
            source=n.get("source", ""),
            url=n.get("url", ""),
            sentiment=None,
            published_at=datetime.fromtimestamp(n.get("datetime", 0), tz=timezone.utc).isoformat(),
        )
        for n in news_items
    ]

    analyst = _analyst_consensus(recommendations)
    score = _composite_score(fundamentals, technicals, analyst, change_pct)

    return ResearchReport(
        ticker=ticker,
        quote=quote,
        fundamentals=fundamentals,
        technicals=technicals,
        news=news,
        analyst_rating=analyst,
        composite_score=score,
        summary=None,
        fetched_at=now.isoformat(),
    )
