import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.database.db import get_db
from app.models.schemas import (
    JournalParseRequest,
    TradeEntryRequest,
    TradeExitRequest,
    TradeRecord,
)
from app.services.journal_parser import parse_trade_message

router = APIRouter(prefix="/api/v1/journal", tags=["Journal"])


def _row_to_trade(row) -> dict:
    return {
        "id": row["id"],
        "trade_id": row["trade_id"],
        "ticker": row["ticker"],
        "direction": row["direction"],
        "entry_date": row["entry_date"],
        "entry_price": row["entry_price"],
        "shares": row["shares"],
        "strategy": row["strategy"],
        "stop_loss": row["stop_loss"],
        "target_price": row["target_price"],
        "risk_reward": row["risk_reward"],
        "mood": row["mood"],
        "status": row["status"],
        "exit_date": row["exit_date"],
        "exit_price": row["exit_price"],
        "pnl_absolute": row["pnl_absolute"],
        "pnl_percent": row["pnl_percent"],
        "created_at": row["created_at"],
    }


@router.post("/entry/parse", response_model=TradeRecord, status_code=201)
async def parse_and_log_trade(req: JournalParseRequest):
    """Parse a natural language trade entry and log it.

    Examples:
        "Bought 50 NVDA at 875 stop 850 target 920"
        "Sold 100 AAPL @ 185.5 sl 180"
    """
    try:
        parsed = parse_trade_message(req.message)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    db = get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        trade_id = str(uuid.uuid4())[:8]

        db.execute(
            """INSERT INTO trades
               (trade_id, ticker, direction, entry_date, entry_price, shares,
                strategy, stop_loss, target_price, risk_reward, raw_message,
                status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)""",
            (
                trade_id,
                parsed["ticker"],
                parsed["direction"],
                now,
                parsed["price"],
                parsed["quantity"],
                parsed["strategy"],
                parsed["stop_loss"],
                parsed["target"],
                parsed["risk_reward"],
                req.message,
                now,
                now,
            ),
        )
        db.commit()
        row = db.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
        return _row_to_trade(row)
    finally:
        db.close()


@router.post("/entry", response_model=TradeRecord, status_code=201)
async def log_trade(req: TradeEntryRequest):
    """Log a structured trade entry."""
    db = get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        trade_id = str(uuid.uuid4())[:8]
        rr = None
        if req.stop_loss and req.target_price:
            risk = abs(req.entry_price - req.stop_loss)
            reward = abs(req.target_price - req.entry_price)
            if risk > 0:
                rr = f"1:{round(reward / risk, 1)}"

        db.execute(
            """INSERT INTO trades
               (trade_id, ticker, direction, entry_date, entry_price, shares,
                strategy, setup_notes, stop_loss, target_price, risk_reward,
                mood, market_condition, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)""",
            (
                trade_id,
                req.ticker.upper(),
                req.direction.upper(),
                now,
                req.entry_price,
                req.shares,
                req.strategy,
                req.setup_notes,
                req.stop_loss,
                req.target_price,
                rr,
                req.mood,
                req.market_condition,
                now,
                now,
            ),
        )
        db.commit()
        row = db.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
        return _row_to_trade(row)
    finally:
        db.close()


@router.post("/exit/{trade_id}", response_model=TradeRecord)
async def close_trade(trade_id: str, req: TradeExitRequest):
    """Close/exit an open trade."""
    db = get_db()
    try:
        row = db.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Trade not found")
        if row["status"] == "CLOSED":
            raise HTTPException(status_code=400, detail="Trade already closed")

        now = datetime.now(timezone.utc).isoformat()
        entry_price = row["entry_price"]
        shares = row["shares"]
        direction = row["direction"]

        if direction == "LONG":
            pnl = (req.exit_price - entry_price) * shares - req.fees
        else:
            pnl = (entry_price - req.exit_price) * shares - req.fees
        pnl_pct = (pnl / (entry_price * shares)) * 100

        db.execute(
            """UPDATE trades SET
               exit_date = ?, exit_price = ?, exit_reason = ?, fees = ?,
               pnl_absolute = ?, pnl_percent = ?, exit_notes = ?,
               status = 'CLOSED', updated_at = ?
               WHERE trade_id = ?""",
            (
                now,
                req.exit_price,
                req.exit_reason,
                req.fees,
                round(pnl, 2),
                round(pnl_pct, 2),
                req.exit_notes,
                now,
                trade_id,
            ),
        )
        db.commit()
        updated = db.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
        return _row_to_trade(updated)
    finally:
        db.close()


@router.get("/trades", response_model=list[TradeRecord])
async def list_trades(status: str | None = None, ticker: str | None = None):
    """List all trades, optionally filtered by status or ticker."""
    db = get_db()
    try:
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status.upper())
        if ticker:
            query += " AND ticker = ?"
            params.append(ticker.upper())
        query += " ORDER BY created_at DESC"
        rows = db.execute(query, params).fetchall()
        return [_row_to_trade(r) for r in rows]
    finally:
        db.close()


@router.get("/trades/{trade_id}", response_model=TradeRecord)
async def get_trade(trade_id: str):
    """Get a single trade by ID."""
    db = get_db()
    try:
        row = db.execute("SELECT * FROM trades WHERE trade_id = ?", (trade_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Trade not found")
        return _row_to_trade(row)
    finally:
        db.close()
