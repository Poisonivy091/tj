"""
AI Stock Trader Service
Analyzes stocks like a professional fund manager at ARK, BlackRock, or a momentum desk.
Uses Claude to reason through each position and generate structured buy/sell/hold signals.
"""
import json
import time
from datetime import datetime, timezone

import anthropic

from app.config.settings import settings
from app.models.schemas import (
    AITradingSignal,
    BreakoutSignal,
    ResearchReport,
    WatchlistScanResult,
)
from app.services.research import deep_research

# ──────────────────────── Fund Style Personas ────────────────────────

FUND_PERSONAS = {
    "ark": {
        "name": "ARK Invest (Cathie Wood style)",
        "philosophy": (
            "You are a portfolio manager at ARK Invest, modeled after Cathie Wood. "
            "You focus exclusively on disruptive innovation: AI, genomics, fintech, autonomous vehicles, "
            "blockchain, and energy storage. You have a 5-year investment horizon. "
            "You are willing to hold high-multiple stocks if the TAM and growth trajectory justify it. "
            "You add to positions on weakness if conviction is high. "
            "You look for exponential growth, S-curve adoption, and platform network effects. "
            "You are NOT concerned with near-term P/E ratios — you care about revenue growth rate, "
            "gross margin expansion, and whether the company is in a winner-take-most market."
        ),
        "position_sizing": "Concentrated positions: 2-10% of portfolio per name. High conviction = larger size.",
        "sell_triggers": "Sell when the innovation thesis is broken, a better disruptor emerges, or valuation becomes extreme even on 5-year DCF.",
    },
    "blackrock": {
        "name": "BlackRock (Factor-Based Systematic)",
        "philosophy": (
            "You are a quantitative portfolio manager at BlackRock. "
            "You run a multi-factor model combining Quality, Momentum, Value, and Low Volatility. "
            "You are systematic and data-driven — you do not chase headlines. "
            "Quality stocks have high ROE, low debt, strong free cash flow, and consistent earnings. "
            "Momentum stocks show 6-12 month relative strength. "
            "Value stocks trade below intrinsic value on P/E, P/B, or EV/EBITDA. "
            "You diversify across sectors and limit concentration risk. "
            "You are risk-adjusted focused: Sharpe ratio, max drawdown, and beta-adjusted returns matter. "
            "ESG overlays apply: you penalize very high-beta or high-short-interest names."
        ),
        "position_sizing": "Diversified positions: 1-3% per name. Risk budget drives sizing. High quality + low vol = slightly larger.",
        "sell_triggers": "Sell when factor scores deteriorate, fundamentals miss guidance, or better risk-adjusted alternatives exist.",
    },
    "momentum": {
        "name": "Technical Momentum Trader",
        "philosophy": (
            "You are an aggressive momentum trader at a hedge fund's equity desk. "
            "You live and die by price action and volume. "
            "You buy breakouts above key resistance, 52-week highs, or consolidation patterns on heavy volume. "
            "You use MACD, RSI, and moving average crossovers to time entries and exits. "
            "Golden cross (SMA50 > SMA200) is bullish, death cross is bearish. "
            "RSI < 30 is oversold (potential reversal buy), RSI > 70 in a strong trend is continuation. "
            "Volume must confirm price moves — a breakout without volume is a false break. "
            "You manage risk tightly: stop loss is placed just below the breakout level or key support. "
            "You hold for days to weeks, not years. You cut losers fast and let winners run."
        ),
        "position_sizing": "Medium positions: 3-7% per trade. Use ATR for stop placement. Risk no more than 1-2% of portfolio per trade.",
        "sell_triggers": "Sell when price breaks below the entry level, volume dries up, or key MA is lost. Trail stops on winners.",
    },
}

# ──────────────────────── Breakout Detection ────────────────────────

def detect_breakouts(report: ResearchReport) -> list[BreakoutSignal]:
    """Scan a research report for technical breakout conditions."""
    signals: list[BreakoutSignal] = []
    now = datetime.now(timezone.utc).isoformat()
    tech = report.technicals
    price = report.quote.current_price

    if price and tech.week_52_high:
        pct_from_high = (price - tech.week_52_high) / tech.week_52_high * 100
        if pct_from_high >= -1.0:
            signals.append(BreakoutSignal(
                signal_type="52W_HIGH_BREAK",
                description=f"Price ${price:.2f} is at or above 52-week high of ${tech.week_52_high:.2f}",
                severity="strong",
                triggered_at=now,
            ))
        elif pct_from_high >= -5.0:
            signals.append(BreakoutSignal(
                signal_type="52W_HIGH_APPROACH",
                description=f"Price ${price:.2f} is within 5% of 52-week high ${tech.week_52_high:.2f}",
                severity="moderate",
                triggered_at=now,
            ))

    if price and tech.week_52_low:
        pct_from_low = (price - tech.week_52_low) / tech.week_52_low * 100
        if pct_from_low <= 5.0:
            signals.append(BreakoutSignal(
                signal_type="52W_LOW_PROXIMITY",
                description=f"Price ${price:.2f} is within 5% of 52-week low ${tech.week_52_low:.2f} — potential bounce or breakdown",
                severity="strong",
                triggered_at=now,
            ))

    if tech.sma_50 and tech.sma_200:
        if tech.sma_50 > tech.sma_200:
            gap_pct = (tech.sma_50 - tech.sma_200) / tech.sma_200 * 100
            severity = "strong" if gap_pct > 5 else "moderate"
            signals.append(BreakoutSignal(
                signal_type="GOLDEN_CROSS",
                description=f"SMA50 (${tech.sma_50}) is above SMA200 (${tech.sma_200}) — bullish long-term trend",
                severity=severity,
                triggered_at=now,
            ))
        else:
            signals.append(BreakoutSignal(
                signal_type="DEATH_CROSS",
                description=f"SMA50 (${tech.sma_50}) is below SMA200 (${tech.sma_200}) — bearish long-term trend",
                severity="strong",
                triggered_at=now,
            ))

    if price and tech.sma_50:
        if price > tech.sma_50 * 1.02:
            signals.append(BreakoutSignal(
                signal_type="PRICE_ABOVE_SMA50",
                description=f"Price ${price:.2f} is trading {((price/tech.sma_50)-1)*100:.1f}% above SMA50 (${tech.sma_50})",
                severity="moderate",
                triggered_at=now,
            ))
        elif price < tech.sma_50 * 0.98:
            signals.append(BreakoutSignal(
                signal_type="PRICE_BELOW_SMA50",
                description=f"Price ${price:.2f} is trading {((tech.sma_50/price)-1)*100:.1f}% below SMA50 (${tech.sma_50}) — key support lost",
                severity="moderate",
                triggered_at=now,
            ))

    if tech.rsi_14:
        if tech.rsi_14 <= 30:
            signals.append(BreakoutSignal(
                signal_type="RSI_OVERSOLD",
                description=f"RSI(14) = {tech.rsi_14:.1f} — deeply oversold, potential reversal buy",
                severity="strong",
                triggered_at=now,
            ))
        elif tech.rsi_14 >= 70:
            signals.append(BreakoutSignal(
                signal_type="RSI_OVERBOUGHT",
                description=f"RSI(14) = {tech.rsi_14:.1f} — overbought, watch for pullback or trend exhaustion",
                severity="moderate",
                triggered_at=now,
            ))
        elif 50 <= tech.rsi_14 < 60:
            signals.append(BreakoutSignal(
                signal_type="RSI_BULLISH_ZONE",
                description=f"RSI(14) = {tech.rsi_14:.1f} — healthy bullish momentum zone",
                severity="weak",
                triggered_at=now,
            ))

    if tech.macd is not None and tech.macd_signal is not None:
        if tech.macd > tech.macd_signal:
            signals.append(BreakoutSignal(
                signal_type="MACD_BULLISH_CROSSOVER",
                description=f"MACD ({tech.macd:.3f}) is above signal ({tech.macd_signal:.3f}) — bullish momentum",
                severity="moderate",
                triggered_at=now,
            ))
        else:
            signals.append(BreakoutSignal(
                signal_type="MACD_BEARISH_CROSSOVER",
                description=f"MACD ({tech.macd:.3f}) is below signal ({tech.macd_signal:.3f}) — bearish momentum",
                severity="moderate",
                triggered_at=now,
            ))

    if report.quote.change_percent:
        if report.quote.change_percent >= 5:
            signals.append(BreakoutSignal(
                signal_type="VOLUME_MOMENTUM_BREAKOUT",
                description=f"Strong single-day move of +{report.quote.change_percent:.1f}% — momentum surge",
                severity="strong",
                triggered_at=now,
            ))
        elif report.quote.change_percent <= -5:
            signals.append(BreakoutSignal(
                signal_type="SHARP_SELLOFF",
                description=f"Sharp single-day decline of {report.quote.change_percent:.1f}% — breakdown or capitulation",
                severity="strong",
                triggered_at=now,
            ))

    return signals


# ──────────────────────── Claude AI Analysis ────────────────────────

def _build_prompt(report: ResearchReport, style: str, breakouts: list[BreakoutSignal]) -> str:
    persona = FUND_PERSONAS.get(style, FUND_PERSONAS["ark"])
    fund_name = persona["name"]
    philosophy = persona["philosophy"]
    position_sizing = persona["position_sizing"]
    sell_triggers = persona["sell_triggers"]

    # Summarise key data points
    q = report.quote
    f = report.fundamentals
    t = report.technicals

    news_summary = "\n".join(
        f"  - [{n.source}] {n.headline}" for n in report.news[:5]
    ) or "  No recent news."

    breakout_summary = "\n".join(
        f"  - [{b.severity.upper()}] {b.signal_type}: {b.description}" for b in breakouts
    ) or "  No strong technical breakouts detected."

    analyst_actions = "\n".join(
        f"  - {a.firm}: {a.action} → {a.to_grade or 'N/A'}" for a in report.analyst_actions[:5]
    ) or "  No recent analyst actions."

    earnings_summary = "\n".join(
        f"  - {e.period}: actual={e.actual}, estimate={e.estimate}, surprise={e.surprise_percent}%"
        for e in report.earnings_history[:4]
    ) or "  No earnings history."

    return f"""You are a portfolio manager at {fund_name}.

{philosophy}

Position Sizing Rule: {position_sizing}
Sell Trigger Rule: {sell_triggers}

---
STOCK: {q.ticker} — {q.company_name}
Current Price: ${q.current_price:.2f} (Change: {q.change_percent:+.2f}%)
Day Range: ${q.day_low:.2f} – ${q.day_high:.2f}

52-Week High: ${t.week_52_high or 'N/A'}   52-Week Low: ${t.week_52_low or 'N/A'}
SMA20: ${t.sma_20 or 'N/A'}  SMA50: ${t.sma_50 or 'N/A'}  SMA200: ${t.sma_200 or 'N/A'}
RSI(14): {t.rsi_14 or 'N/A'}  MACD: {t.macd or 'N/A'}  ATR: {t.atr or 'N/A'}  Beta: {t.beta or 'N/A'}

Fundamentals:
  P/E: {f.pe_ratio or 'N/A'}  PEG: {f.peg_ratio or 'N/A'}  P/B: {f.pb_ratio or 'N/A'}
  ROE: {f.roe or 'N/A'}%  Revenue Growth: {f.revenue_growth or 'N/A'}%  EPS Growth: {f.eps_growth or 'N/A'}%
  Profit Margin: {f.profit_margin or 'N/A'}%  Debt/Equity: {f.debt_equity or 'N/A'}
  Market Cap: ${f.market_cap or 'N/A'}  Free Cash Flow: ${f.free_cash_flow or 'N/A'}
  Short Interest: {f.short_percent_of_float or 'N/A'}% of float
  Analyst Rating: {report.analyst_rating or 'N/A'}
  Composite Score: {report.composite_score or 'N/A'}/100

Price Target (consensus):
  Mean: ${report.price_targets.target_mean if report.price_targets else 'N/A'}
  High: ${report.price_targets.target_high if report.price_targets else 'N/A'}
  Low: ${report.price_targets.target_low if report.price_targets else 'N/A'}

Technical Breakout Signals:
{breakout_summary}

Recent Analyst Actions:
{analyst_actions}

Earnings Surprise History:
{earnings_summary}

Recent News:
{news_summary}
---

Based on this data and your fund's investment philosophy, provide a trading decision.
Respond ONLY with a valid JSON object in exactly this format (no markdown, no extra text):

{{
  "action": "BUY" | "SELL" | "HOLD" | "WATCH",
  "conviction": <integer 1-10>,
  "entry_range_low": <float or null>,
  "entry_range_high": <float or null>,
  "stop_loss": <float or null>,
  "price_target": <float or null>,
  "target_horizon": "<string e.g. '3-6 months'>",
  "position_size_pct": <float, % of portfolio, or null>,
  "reasoning": "<2-4 sentence explanation from your fund's perspective>",
  "key_catalysts": ["<catalyst 1>", "<catalyst 2>", "<catalyst 3>"],
  "key_risks": ["<risk 1>", "<risk 2>", "<risk 3>"]
}}"""


def _call_claude(prompt: str) -> dict:
    """Call Claude API and parse JSON response."""
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ──────────────────────── Main Signal Generator ────────────────────────

async def generate_signal(ticker: str, style: str = "ark") -> AITradingSignal:
    """Full pipeline: research → breakout detection → Claude analysis → signal."""
    style = style.lower()
    if style not in FUND_PERSONAS:
        style = "ark"

    report = await deep_research(ticker)
    breakouts = detect_breakouts(report)

    now = datetime.now(timezone.utc).isoformat()

    if not settings.ANTHROPIC_API_KEY:
        # Fallback: rule-based signal when no API key
        action = "HOLD"
        conviction = 5
        if report.composite_score and report.composite_score >= 70:
            action = "BUY"
            conviction = 7
        elif report.composite_score and report.composite_score <= 35:
            action = "SELL"
            conviction = 6
        elif any(b.signal_type in ("52W_HIGH_BREAK", "GOLDEN_CROSS") for b in breakouts):
            action = "BUY"
            conviction = 6

        return AITradingSignal(
            ticker=ticker.upper(),
            fund_style=style,
            action=action,
            conviction=conviction,
            entry_price=report.quote.current_price,
            stop_loss=round(report.quote.current_price * 0.93, 2) if action == "BUY" else None,
            price_target=round(report.quote.current_price * 1.20, 2) if action == "BUY" else None,
            target_horizon="3-6 months",
            position_size_pct=3.0,
            reasoning="Rule-based signal (no Claude API key configured). Set ANTHROPIC_API_KEY for AI analysis.",
            key_catalysts=[f"Composite score: {report.composite_score}/100"],
            key_risks=["No AI analysis available"],
            breakout_signals=breakouts,
            composite_score=report.composite_score,
            current_price=report.quote.current_price,
            generated_at=now,
        )

    prompt = _build_prompt(report, style, breakouts)
    result = _call_claude(prompt)

    return AITradingSignal(
        ticker=ticker.upper(),
        fund_style=style,
        action=result.get("action", "HOLD"),
        conviction=int(result.get("conviction", 5)),
        entry_price=report.quote.current_price,
        entry_range_low=result.get("entry_range_low"),
        entry_range_high=result.get("entry_range_high"),
        stop_loss=result.get("stop_loss"),
        price_target=result.get("price_target"),
        target_horizon=result.get("target_horizon"),
        position_size_pct=result.get("position_size_pct"),
        reasoning=result.get("reasoning", ""),
        key_catalysts=result.get("key_catalysts", []),
        key_risks=result.get("key_risks", []),
        breakout_signals=breakouts,
        composite_score=report.composite_score,
        current_price=report.quote.current_price,
        generated_at=now,
    )


# ──────────────────────── Watchlist Scanner ────────────────────────

async def scan_watchlist(style: str = "ark", min_conviction: int = 6) -> WatchlistScanResult:
    """Scan all watchlist tickers and generate AI signals."""
    from app.database.db import get_db
    import asyncio

    db = get_db()
    try:
        rows = db.execute("SELECT DISTINCT ticker FROM watchlist").fetchall()
        tickers = [r["ticker"] for r in rows]
    finally:
        db.close()

    t_start = time.time()
    now = datetime.now(timezone.utc).isoformat()

    buy_signals: list[AITradingSignal] = []
    sell_signals: list[AITradingSignal] = []
    watch_signals: list[AITradingSignal] = []

    # Process sequentially to avoid rate limiting
    for ticker in tickers:
        try:
            signal = await generate_signal(ticker, style)
            _save_signal(signal)
            if signal.conviction >= min_conviction:
                if signal.action == "BUY":
                    buy_signals.append(signal)
                elif signal.action == "SELL":
                    sell_signals.append(signal)
                elif signal.action in ("HOLD", "WATCH"):
                    watch_signals.append(signal)
        except Exception:
            continue

    duration = round(time.time() - t_start, 2)
    total_signals = len(buy_signals) + len(sell_signals) + len(watch_signals)

    return WatchlistScanResult(
        scanned=len(tickers),
        signals_generated=total_signals,
        buy_signals=buy_signals,
        sell_signals=sell_signals,
        watch_signals=watch_signals,
        scan_duration_seconds=duration,
        scanned_at=now,
    )


def _save_signal(signal: AITradingSignal) -> int:
    """Persist an AI signal to the database. Returns the new row id."""
    from app.database.db import get_db
    db = get_db()
    try:
        cursor = db.execute(
            """INSERT INTO ai_signals
               (ticker, fund_style, action, conviction, entry_price, entry_range_low, entry_range_high,
                stop_loss, price_target, target_horizon, position_size_pct, reasoning,
                key_catalysts, key_risks, breakout_signals, composite_score, current_price, generated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                signal.ticker,
                signal.fund_style,
                signal.action,
                signal.conviction,
                signal.entry_price,
                signal.entry_range_low,
                signal.entry_range_high,
                signal.stop_loss,
                signal.price_target,
                signal.target_horizon,
                signal.position_size_pct,
                signal.reasoning,
                json.dumps(signal.key_catalysts),
                json.dumps(signal.key_risks),
                json.dumps([b.model_dump() for b in signal.breakout_signals]),
                signal.composite_score,
                signal.current_price,
                signal.generated_at,
            ),
        )
        db.commit()
        return cursor.lastrowid
    finally:
        db.close()
