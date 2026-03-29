from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database.db import init_db
from app.routers import analytics, journal, notifications, research, watchlist
from app.routers import ai_trader


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Trading Journal API",
    description="AI-powered stock research, watchlist monitoring, trade journaling, P&L tracking, and WhatsApp notifications.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(research.router)
app.include_router(watchlist.router)
app.include_router(journal.router)
app.include_router(analytics.router)
app.include_router(notifications.router)
app.include_router(ai_trader.router)


@app.get("/")
async def root():
    return {
        "name": "Trading Journal API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "research": "GET /api/v1/research/{ticker}",
            "watchlist": "POST /api/v1/watchlist",
            "watchlist_list": "GET /api/v1/watchlist",
            "alerts": "POST /api/v1/watchlist/alerts",
            "journal_parse": "POST /api/v1/journal/entry/parse",
            "journal_entry": "POST /api/v1/journal/entry",
            "journal_exit": "POST /api/v1/journal/exit/{trade_id}",
            "trades": "GET /api/v1/journal/trades",
            "analytics": "GET /api/v1/analytics/performance",
            "strategies": "GET /api/v1/analytics/strategies",
            "whatsapp": "POST /api/v1/notifications/whatsapp",
            "ai_analyze": "POST /api/v1/ai-trader/analyze/{ticker}",
            "ai_scan": "POST /api/v1/ai-trader/scan",
            "ai_signals": "GET /api/v1/ai-trader/signals",
            "ai_breakouts": "GET /api/v1/ai-trader/breakouts/{ticker}",
            "ai_execute": "POST /api/v1/ai-trader/execute",
            "ai_portfolio": "GET /api/v1/ai-trader/portfolio",
            "ai_styles": "GET /api/v1/ai-trader/styles",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
