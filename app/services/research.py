import asyncio
from datetime import datetime, timedelta, timezone

import numpy as np

from app.integrations.yahoo_client import fetch_yahoo_chart, fetch_yahoo_quote
from app.integrations.finnhub_client import (
    get_basic_financials,
    get_company_news,
    get_earnings_surprises,
    get_price_target,
    get_recommendation_trends,
    get_upgrade_downgrade,
)
from app.integrations.alphavantage_client import get_company_overview, get_global_quote
from app.integrations.newsapi_client import search_news
from app.integrations.sec_client import search_company_filings, get_insider_trades, get_company_tickers_cik
from app.models.schemas import (
    AnalystAction,
    AnalystPriceTarget,
    DataSources,
    EarningsSurprise,
    FundamentalData,
    InsiderTrade,
    NewsSentiment,
    PriceData,
    ResearchReport,
    SECFiling,
    StockQuote,
    TechnicalData,
)


# ──────────────────────── Technical Helpers ────────────────────────

def _sma(prices: list[float], window: int) -> float | None:
    if len(prices) < window:
        return None
    return round(float(np.mean(prices[-window:])), 2)


def _ema(prices: list[float], window: int) -> float | None:
    if len(prices) < window:
        return None
    arr = np.array(prices[-window * 2:], dtype=float)
    weights = np.exp(np.linspace(-1.0, 0.0, len(arr)))
    weights /= weights.sum()
    return round(float(np.dot(arr, weights)), 2)


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


def _macd(prices: list[float]) -> tuple[float | None, float | None]:
    """MACD (12,26,9). Returns (macd_line, signal_line)."""
    if len(prices) < 35:
        return None, None
    ema12 = _ema(prices, 12)
    ema26 = _ema(prices, 26)
    if ema12 is None or ema26 is None:
        return None, None
    macd_line = round(ema12 - ema26, 4)
    # Approximate signal as 9-day EMA of recent MACD-like values
    signal = _ema(prices[-9:], 9)
    return macd_line, signal


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


# ──────────────────────── Scoring Helpers ────────────────────────

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
    """0-100 composite score combining fundamentals, technicals, and analyst consensus."""
    score = 50

    # Fundamentals
    if fundamentals.pe_ratio and 0 < fundamentals.pe_ratio < 25:
        score += 5
    if fundamentals.peg_ratio and 0 < fundamentals.peg_ratio < 1.5:
        score += 5
    if fundamentals.roe and fundamentals.roe > 15:
        score += 5
    if fundamentals.debt_equity is not None and fundamentals.debt_equity < 1:
        score += 5
    if fundamentals.revenue_growth and fundamentals.revenue_growth > 0:
        score += 5
    if fundamentals.profit_margin and fundamentals.profit_margin > 15:
        score += 3
    if fundamentals.short_percent_of_float and fundamentals.short_percent_of_float > 20:
        score -= 5  # high short interest = risk

    # Technicals
    if technicals.rsi_14:
        if technicals.rsi_14 < 30:
            score += 10
        elif technicals.rsi_14 > 70:
            score -= 10

    if technicals.sma_50 and technicals.sma_200:
        if technicals.sma_50 > technicals.sma_200:
            score += 5  # golden cross
        else:
            score -= 3  # death cross

    if technicals.macd and technicals.macd_signal:
        if technicals.macd > technicals.macd_signal:
            score += 3
        else:
            score -= 3

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


# ──────────────────────── Safe fetchers ────────────────────────

async def _safe(coro, default=None):
    """Run a coroutine and return default on any error."""
    try:
        return await coro
    except Exception:
        return default


# ──────────────────────── Main Research ────────────────────────

async def deep_research(ticker: str) -> ResearchReport:
    """Run comprehensive research pulling from all available sources."""
    ticker = ticker.upper()
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    sources = DataSources()

    # ── Parallel fetch from all sources ──
    (
        quote_data,
        chart_data,
        financials,
        recommendations,
        finnhub_news,
        price_target_data,
        upgrade_downgrade_data,
        earnings_data,
        av_overview,
        av_quote,
        newsapi_articles,
        sec_filings_10k,
        sec_filings_10q,
        sec_filings_8k,
    ) = await asyncio.gather(
        _safe(fetch_yahoo_quote(ticker), {}),
        _safe(fetch_yahoo_chart(ticker), {}),
        _safe(get_basic_financials(ticker), {}),
        _safe(get_recommendation_trends(ticker), []),
        _safe(get_company_news(ticker, month_ago, today), []),
        _safe(get_price_target(ticker), {}),
        _safe(get_upgrade_downgrade(ticker), []),
        _safe(get_earnings_surprises(ticker), []),
        _safe(get_company_overview(ticker), {}),
        _safe(get_global_quote(ticker), {}),
        _safe(search_news(f"{ticker} stock"), []),
        _safe(search_company_filings(ticker, "10-K", 3), []),
        _safe(search_company_filings(ticker, "10-Q", 3), []),
        _safe(search_company_filings(ticker, "8-K", 5), []),
    )

    # Track which sources returned data
    if quote_data:
        sources.yahoo_finance = True
    if financials and financials.get("metric"):
        sources.finnhub = True
    if av_overview and av_overview.get("Symbol"):
        sources.alpha_vantage = True
    if newsapi_articles:
        sources.newsapi = True

    # SEC insider trades (needs CIK, do separately)
    insider_list = []
    try:
        cik = await get_company_tickers_cik(ticker)
        if cik:
            insider_raw = await get_insider_trades(str(cik), 10)
            insider_list = insider_raw
            if insider_raw:
                sources.sec_edgar = True
    except Exception:
        pass

    if sec_filings_10k or sec_filings_10q or sec_filings_8k:
        sources.sec_edgar = True

    # ── Parse chart for technicals ──
    chart_result = chart_data.get("chart", {}).get("result", [{}])[0] if chart_data else {}
    chart_indicators = chart_result.get("indicators", {}).get("quote", [{}])[0]
    closes = [c for c in (chart_indicators.get("close") or []) if c is not None]
    highs_list = [h for h in (chart_indicators.get("high") or []) if h is not None]
    lows_list = [l for l in (chart_indicators.get("low") or []) if l is not None]
    meta = chart_result.get("meta", {})

    # ── Build PriceData (regular + extended hours) ──
    regular_price = quote_data.get("current_price", 0) if quote_data else 0
    prev_close = quote_data.get("previous_close", 0) if quote_data else 0
    change_amt = round(regular_price - prev_close, 2) if prev_close else 0
    change_pct = round((change_amt / prev_close * 100) if prev_close else 0, 2)

    price_data = PriceData(
        regular_market_price=regular_price,
        previous_close=prev_close,
        open_price=quote_data.get("open_price", 0) if quote_data else 0,
        day_high=quote_data.get("day_high", 0) if quote_data else 0,
        day_low=quote_data.get("day_low", 0) if quote_data else 0,
        change_amount=change_amt,
        change_percent=change_pct,
        post_market_price=quote_data.get("post_market_price") if quote_data else None,
        post_market_change=quote_data.get("post_market_change") if quote_data else None,
        post_market_change_percent=quote_data.get("post_market_change_percent") if quote_data else None,
        pre_market_price=quote_data.get("pre_market_price") if quote_data else None,
        pre_market_change=quote_data.get("pre_market_change") if quote_data else None,
        pre_market_change_percent=quote_data.get("pre_market_change_percent") if quote_data else None,
    )

    # ── Build fundamentals (merge Finnhub + Alpha Vantage) ──
    fh_metric = financials.get("metric", {}) if financials else {}
    av = av_overview or {}

    def _float(val):
        if val is None or val == "" or val == "None" or val == "-":
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    fundamentals = FundamentalData(
        pe_ratio=fh_metric.get("peNormalizedAnnual") or _float(av.get("PERatio")),
        peg_ratio=_float(av.get("PEGRatio")),
        pb_ratio=fh_metric.get("pbAnnual") or _float(av.get("PriceToBookRatio")),
        ps_ratio=fh_metric.get("psAnnual") or _float(av.get("PriceToSalesRatioTTM")),
        roe=fh_metric.get("roeTTM") or _float(av.get("ReturnOnEquityTTM")),
        roa=_float(av.get("ReturnOnAssetsTTM")),
        debt_equity=fh_metric.get("totalDebt/totalEquityAnnual"),
        current_ratio=fh_metric.get("currentRatioAnnual") or _float(av.get("CurrentRatio")),
        free_cash_flow=fh_metric.get("freeCashFlowTTM"),
        operating_margin=_float(av.get("OperatingMarginTTM")),
        profit_margin=_float(av.get("ProfitMargin")),
        revenue_growth=fh_metric.get("revenueGrowthTTMAnnual") or _float(av.get("QuarterlyRevenueGrowthYOY")),
        eps_growth=fh_metric.get("epsGrowthTTMAnnual") or _float(av.get("QuarterlyEarningsGrowthYOY")),
        eps_ttm=_float(av.get("EPS")),
        dividend_yield=fh_metric.get("dividendYieldIndicatedAnnual") or _float(av.get("DividendYield")),
        market_cap=fh_metric.get("marketCapitalization") or _float(av.get("MarketCapitalization")),
        enterprise_value=_float(av.get("EVToRevenue")),
        shares_outstanding=_float(av.get("SharesOutstanding")),
        short_percent_of_float=fh_metric.get("shortInterestPercentOfFloat"),
        earnings_date=av.get("LatestQuarter"),
    )

    # ── Build technicals ──
    macd_val, macd_sig = _macd(closes)
    technicals = TechnicalData(
        sma_20=_sma(closes, 20),
        sma_50=_sma(closes, 50),
        sma_200=_sma(closes, 200) if len(closes) >= 200 else None,
        rsi_14=_rsi(closes),
        week_52_high=meta.get("fiftyTwoWeekHigh") or fh_metric.get("52WeekHigh") or _float(av.get("52WeekHigh")),
        week_52_low=meta.get("fiftyTwoWeekLow") or fh_metric.get("52WeekLow") or _float(av.get("52WeekLow")),
        beta=fh_metric.get("beta") or _float(av.get("Beta")),
        atr=_atr(highs_list, lows_list, closes),
        macd=macd_val,
        macd_signal=macd_sig,
    )

    # ── Build quote ──
    quote = StockQuote(
        ticker=ticker,
        company_name=quote_data.get("company_name", av.get("Name", ticker)) if quote_data else av.get("Name", ticker),
        current_price=regular_price,
        change_percent=change_pct,
        day_high=price_data.day_high,
        day_low=price_data.day_low,
        open_price=price_data.open_price,
        previous_close=prev_close,
        volume=quote_data.get("volume", 0) if quote_data else 0,
        price_data=price_data,
    )

    # ── Build news (merge Finnhub + NewsAPI, deduplicated) ──
    news = []
    seen_headlines = set()

    for n in (finnhub_news or [])[:10]:
        headline = n.get("headline", "")
        if headline and headline not in seen_headlines:
            seen_headlines.add(headline)
            news.append(NewsSentiment(
                headline=headline,
                source=n.get("source", "Finnhub"),
                url=n.get("url", ""),
                sentiment=None,
                published_at=datetime.fromtimestamp(n.get("datetime", 0), tz=timezone.utc).isoformat(),
            ))

    for a in (newsapi_articles or [])[:10]:
        headline = a.get("title", "")
        if headline and headline not in seen_headlines:
            seen_headlines.add(headline)
            news.append(NewsSentiment(
                headline=headline,
                source=a.get("source", {}).get("name", "NewsAPI"),
                url=a.get("url", ""),
                sentiment=None,
                published_at=a.get("publishedAt", ""),
            ))

    # ── Build SEC filings ──
    sec_filings = []
    for filing_list in [sec_filings_10k, sec_filings_10q, sec_filings_8k]:
        for f in (filing_list or []):
            sec_filings.append(SECFiling(
                form_type=f.get("form_type", ""),
                filed_at=f.get("filed_at", ""),
                description=f.get("description", ""),
                url=f.get("url", ""),
            ))

    # ── Build insider trades ──
    insiders = [
        InsiderTrade(
            filed_at=i.get("filed_at", ""),
            filer=i.get("filer", ""),
            form_type=i.get("form_type", "4"),
        )
        for i in (insider_list or [])
    ]

    # ── Build analyst price targets (TipRanks-style) ──
    price_targets = None
    if price_target_data and price_target_data.get("targetMean"):
        price_targets = AnalystPriceTarget(
            target_high=price_target_data.get("targetHigh"),
            target_low=price_target_data.get("targetLow"),
            target_mean=price_target_data.get("targetMean"),
            target_median=price_target_data.get("targetMedian"),
            number_of_analysts=price_target_data.get("lastUpdated") and len(recommendations) if recommendations else None,
            last_updated=price_target_data.get("lastUpdated"),
        )

    # ── Build analyst upgrade/downgrade actions (firm-level ratings) ──
    analyst_actions = []
    for ud in (upgrade_downgrade_data or [])[:20]:
        analyst_actions.append(AnalystAction(
            firm=ud.get("company", "Unknown"),
            action=ud.get("action", ""),
            from_grade=ud.get("fromGrade"),
            to_grade=ud.get("toGrade"),
            date=ud.get("gradeTime", ""),
        ))

    # ── Build earnings surprise history ──
    earnings_history = []
    for e in (earnings_data or [])[:8]:
        actual = e.get("actual")
        estimate = e.get("estimate")
        surprise = None
        surprise_pct = None
        if actual is not None and estimate is not None and estimate != 0:
            surprise = round(actual - estimate, 4)
            surprise_pct = round((surprise / abs(estimate)) * 100, 2)
        earnings_history.append(EarningsSurprise(
            period=e.get("period", ""),
            actual=actual,
            estimate=estimate,
            surprise=surprise,
            surprise_percent=surprise_pct,
        ))

    analyst = _analyst_consensus(recommendations or [])
    score = _composite_score(fundamentals, technicals, analyst, change_pct)

    return ResearchReport(
        ticker=ticker,
        quote=quote,
        fundamentals=fundamentals,
        technicals=technicals,
        news=news,
        sec_filings=sec_filings,
        insider_trades=insiders,
        price_targets=price_targets,
        analyst_actions=analyst_actions,
        earnings_history=earnings_history,
        analyst_rating=analyst,
        composite_score=score,
        summary=None,
        data_sources=sources,
        fetched_at=now.isoformat(),
    )
