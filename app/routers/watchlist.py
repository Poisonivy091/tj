from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.database.db import get_db
from app.models.schemas import (
    AlertCreateRequest,
    AlertItem,
    WatchlistAddRequest,
    WatchlistItem,
)

router = APIRouter(prefix="/api/v1/watchlist", tags=["Watchlist"])


@router.get("", response_model=list[WatchlistItem])
async def list_watchlist(category: str | None = None):
    """List all watchlist items, optionally filtered by category."""
    db = get_db()
    try:
        if category:
            rows = db.execute(
                "SELECT * FROM watchlist WHERE category = ? ORDER BY added_at DESC",
                (category,),
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM watchlist ORDER BY added_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


@router.post("", response_model=WatchlistItem, status_code=201)
async def add_to_watchlist(req: WatchlistAddRequest):
    """Add a ticker to the watchlist."""
    db = get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cursor = db.execute(
            "INSERT INTO watchlist (ticker, category, notes, added_at) VALUES (?, ?, ?, ?)",
            (req.ticker.upper(), req.category, req.notes, now),
        )
        db.commit()
        row = db.execute("SELECT * FROM watchlist WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)
    finally:
        db.close()


@router.delete("/{item_id}")
async def remove_from_watchlist(item_id: int):
    """Remove a ticker from the watchlist."""
    db = get_db()
    try:
        deleted = db.execute("DELETE FROM watchlist WHERE id = ?", (item_id,)).rowcount
        db.commit()
        if not deleted:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"status": "deleted", "id": item_id}
    finally:
        db.close()


# ──────────────────────────── Alerts ────────────────────────────

@router.post("/alerts", response_model=AlertItem, status_code=201)
async def create_alert(req: AlertCreateRequest):
    """Create a price/condition alert for a ticker."""
    db = get_db()
    try:
        now = datetime.now(timezone.utc).isoformat()
        cursor = db.execute(
            "INSERT INTO alerts (ticker, condition_type, threshold, operator, created_at) VALUES (?, ?, ?, ?, ?)",
            (req.ticker.upper(), req.condition_type, req.threshold, req.operator, now),
        )
        db.commit()
        row = db.execute("SELECT * FROM alerts WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)
    finally:
        db.close()


@router.get("/alerts", response_model=list[AlertItem])
async def list_alerts(ticker: str | None = None):
    """List all alerts, optionally filtered by ticker."""
    db = get_db()
    try:
        if ticker:
            rows = db.execute(
                "SELECT * FROM alerts WHERE ticker = ? ORDER BY created_at DESC",
                (ticker.upper(),),
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM alerts ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


@router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: int):
    """Delete an alert."""
    db = get_db()
    try:
        deleted = db.execute("DELETE FROM alerts WHERE id = ?", (alert_id,)).rowcount
        db.commit()
        if not deleted:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"status": "deleted", "id": alert_id}
    finally:
        db.close()
