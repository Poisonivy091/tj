"""
AI Trader Router
Endpoints for AI-powered signal generation, watchlist scanning, and virtual portfolio management.
"""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.database.db import get_db
from app.models.schemas import (
    AIPortfolioPosition,
    AIPortfolioSummary,
    AITradingSignal,
    BreakoutSignal,
    ExecuteTradeRequest,
    StyleConfigRequest,
    WatchlistScanRequest,
    WatchlistScanResult,
)
from app.services.ai_trader import generate_signal, scan_watchlist, _save_signal

router = APIRouter(prefix="/api/v1/ai-trader", tags=["AI Trader"])


# ──────────────────────────── Helpers ────────────────────────────────

def _row_to_signal(row: dict) -> AITradingSignal:
    return AITradingSignal(
        id=row["id"],
        ticker=row["ticker"],
        fund_style=row["fund_style"],
        action=row["action"],
        conviction=row["conviction"],
        entry_price=row.get("entry_price"),
        entry_range_low=row.get("entry_range_low"),
        entry_range_high=row.get("entry_range_high"),
        stop_loss=row.get("stop_loss"),
        price_target=row.get("price_target"),
        target_horizon=row.get("target_horizon"),
        position_size_pct=row.get("position_size_pct"),
        reasoning=row["reasoning"],
        key_catalysts=json.loads(row.get("key_catalysts") or "[]"),
        key_risks=json.loads(row.get("key_risks") or "[]"),
        breakout_signals=[
            BreakoutSignal(**b)
            for b in json.loads(row.get("breakout_signals") or "[]")
        ],
        composite_score=row.get("composite_score"),
        current_price=row.get("current_price"),
        generated_at=row["generated_at"],
    )


def _row_to_position(row: dict) -> AIPortfolioPosition:
    return AIPortfolioPosition(
        id=row["id"],
        ticker=row["ticker"],
        direction=row["direction"],
        shares=row["shares"],
        entry_price=row["entry_price"],
        current_price=row.get("current_price"),
        stop_loss=row.get("stop_loss"),
        price_target=row.get("price_target"),
        fund_style=row["fund_style"],
        conviction=row["conviction"],
        reasoning=row["reasoning"],
        status=row["status"],
        pnl_absolute=row.get("pnl_absolute"),
        pnl_percent=row.get("pnl_percent"),
        opened_at=row["opened_at"],
        closed_at=row.get("closed_at"),
    )


# ──────────────────────────── Signal Endpoints ────────────────────────────────

@router.post("/analyze/{ticker}", response_model=AITradingSignal)
async def analyze_ticker(ticker: str, fund_style: str = "ark"):
    """
    Run a full AI analysis on a single ticker.
    The AI reasons like a fund manager at ARK, BlackRock, or a momentum desk.
    """
    try:
        signal = await generate_signal(ticker.upper(), fund_style)
        _save_signal(signal)
        return signal
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan", response_model=WatchlistScanResult)
async def scan_all_watchlist(req: WatchlistScanRequest):
    """
    Scan every ticker on your watchlist with the AI trader.
    Returns buy/sell/hold signals sorted by conviction.
    """
    try:
        result = await scan_watchlist(req.fund_style, req.min_conviction)
        # Sort by conviction descending
        result.buy_signals.sort(key=lambda s: s.conviction, reverse=True)
        result.sell_signals.sort(key=lambda s: s.conviction, reverse=True)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals", response_model=list[AITradingSignal])
async def list_signals(
    ticker: Optional[str] = None,
    fund_style: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 50,
):
    """List previously generated AI signals, newest first."""
    db = get_db()
    try:
        query = "SELECT * FROM ai_signals WHERE 1=1"
        params: list = []
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker.upper())
        if fund_style:
            query += " AND fund_style = ?"
            params.append(fund_style.lower())
        if action:
            query += " AND action = ?"
            params.append(action.upper())
        query += " ORDER BY generated_at DESC LIMIT ?"
        params.append(limit)
        rows = db.execute(query, params).fetchall()
        return [_row_to_signal(dict(r)) for r in rows]
    finally:
        db.close()


@router.delete("/signals/{signal_id}")
async def delete_signal(signal_id: int):
    db = get_db()
    try:
        deleted = db.execute("DELETE FROM ai_signals WHERE id = ?", (signal_id,)).rowcount
        db.commit()
        if not deleted:
            raise HTTPException(status_code=404, detail="Signal not found")
        return {"status": "deleted", "id": signal_id}
    finally:
        db.close()


# ──────────────────────────── Portfolio Endpoints ────────────────────────────────

@router.post("/execute", response_model=AIPortfolioPosition, status_code=201)
async def execute_trade(req: ExecuteTradeRequest):
    """
    Generate an AI signal and, if BUY or SELL, open/close a virtual portfolio position.
    If force_action is set, overrides the AI's action.
    """
    signal = await generate_signal(req.ticker, req.fund_style)
    _save_signal(signal)

    action = req.force_action.upper() if req.force_action else signal.action

    if action not in ("BUY", "SELL"):
        raise HTTPException(
            status_code=200,
            detail=f"AI action is {signal.action} (conviction {signal.conviction}/10). No trade executed. Reason: {signal.reasoning}",
        )

    db = get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()

        if action == "BUY":
            position_pct = (signal.position_size_pct or 3.0) / 100
            position_value = req.portfolio_value * position_pct
            price = signal.current_price or signal.entry_price or 1.0
            shares = round(position_value / price, 4)

            cursor = db.execute(
                """INSERT INTO ai_portfolio
                   (ticker, direction, shares, entry_price, current_price, stop_loss, price_target,
                    fund_style, conviction, reasoning, status, opened_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    signal.ticker,
                    "LONG",
                    shares,
                    price,
                    price,
                    signal.stop_loss,
                    signal.price_target,
                    signal.fund_style,
                    signal.conviction,
                    signal.reasoning,
                    "OPEN",
                    now,
                ),
            )
            db.commit()
            row = db.execute("SELECT * FROM ai_portfolio WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return _row_to_position(dict(row))

        else:  # SELL — close any open long position
            open_pos = db.execute(
                "SELECT * FROM ai_portfolio WHERE ticker = ? AND status = 'OPEN' ORDER BY opened_at DESC LIMIT 1",
                (signal.ticker,),
            ).fetchone()
            if not open_pos:
                raise HTTPException(status_code=404, detail=f"No open position found for {signal.ticker}")

            price = signal.current_price or signal.entry_price or open_pos["entry_price"]
            pnl_abs = round((price - open_pos["entry_price"]) * open_pos["shares"], 2)
            pnl_pct = round((price - open_pos["entry_price"]) / open_pos["entry_price"] * 100, 2)

            db.execute(
                """UPDATE ai_portfolio SET status='CLOSED', current_price=?, pnl_absolute=?,
                   pnl_percent=?, closed_at=? WHERE id=?""",
                (price, pnl_abs, pnl_pct, now, open_pos["id"]),
            )
            db.commit()
            row = db.execute("SELECT * FROM ai_portfolio WHERE id = ?", (open_pos["id"],)).fetchone()
            return _row_to_position(dict(row))
    finally:
        db.close()


@router.get("/portfolio", response_model=AIPortfolioSummary)
async def get_portfolio(fund_style: Optional[str] = None, refresh_prices: bool = False):
    """
    View the AI-managed virtual portfolio.
    Set refresh_prices=true to fetch current market prices and recalculate P&L.
    """
    db = get_db()
    try:
        if fund_style:
            rows = db.execute(
                "SELECT * FROM ai_portfolio WHERE fund_style = ? ORDER BY opened_at DESC",
                (fund_style.lower(),),
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM ai_portfolio ORDER BY opened_at DESC").fetchall()

        positions = [_row_to_position(dict(r)) for r in rows]
        now = datetime.now(timezone.utc).isoformat()

        if refresh_prices:
            from app.integrations.yahoo_client import fetch_yahoo_quote
            for pos in positions:
                if pos.status == "OPEN":
                    try:
                        quote = await fetch_yahoo_quote(pos.ticker)
                        current = quote.get("current_price", pos.entry_price)
                        pnl_abs = round((current - pos.entry_price) * pos.shares, 2)
                        pnl_pct = round((current - pos.entry_price) / pos.entry_price * 100, 2)
                        db.execute(
                            "UPDATE ai_portfolio SET current_price=?, pnl_absolute=?, pnl_percent=? WHERE id=?",
                            (current, pnl_abs, pnl_pct, pos.id),
                        )
                        pos.current_price = current
                        pos.pnl_absolute = pnl_abs
                        pos.pnl_percent = pnl_pct
                    except Exception:
                        pass
            db.commit()

        open_positions = [p for p in positions if p.status == "OPEN"]
        total_unrealized = sum(p.pnl_absolute or 0 for p in open_positions)

        return AIPortfolioSummary(
            positions=positions,
            total_positions=len(positions),
            open_positions=len(open_positions),
            total_unrealized_pnl=round(total_unrealized, 2),
            style=fund_style or "mixed",
            last_updated=now,
        )
    finally:
        db.close()


@router.delete("/portfolio/{position_id}")
async def close_position(position_id: int, exit_price: Optional[float] = None):
    """Manually close a virtual portfolio position."""
    db = get_db()
    try:
        row = db.execute("SELECT * FROM ai_portfolio WHERE id = ?", (position_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Position not found")
        if row["status"] == "CLOSED":
            raise HTTPException(status_code=400, detail="Position is already closed")

        price = exit_price or row["current_price"] or row["entry_price"]
        pnl_abs = round((price - row["entry_price"]) * row["shares"], 2)
        pnl_pct = round((price - row["entry_price"]) / row["entry_price"] * 100, 2)
        now = datetime.now(timezone.utc).isoformat()

        db.execute(
            "UPDATE ai_portfolio SET status='CLOSED', current_price=?, pnl_absolute=?, pnl_percent=?, closed_at=? WHERE id=?",
            (price, pnl_abs, pnl_pct, now, position_id),
        )
        db.commit()
        row = db.execute("SELECT * FROM ai_portfolio WHERE id = ?", (position_id,)).fetchone()
        return _row_to_position(dict(row))
    finally:
        db.close()


# ──────────────────────────── Breakout-Only Scan ────────────────────────────────

@router.get("/breakouts/{ticker}", response_model=list[BreakoutSignal])
async def get_breakouts(ticker: str):
    """
    Fast technical breakout scan for a single ticker without full AI analysis.
    Returns all detected breakout conditions immediately.
    """
    from app.services.research import deep_research
    from app.services.ai_trader import detect_breakouts
    try:
        report = await deep_research(ticker.upper())
        return detect_breakouts(report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/styles")
async def list_styles():
    """List available fund manager styles and their investment philosophies."""
    from app.services.ai_trader import FUND_PERSONAS
    return {
        style: {
            "name": p["name"],
            "philosophy": p["philosophy"],
            "position_sizing": p["position_sizing"],
            "sell_triggers": p["sell_triggers"],
        }
        for style, p in FUND_PERSONAS.items()
    }
