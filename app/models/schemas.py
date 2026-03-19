from pydantic import BaseModel
from typing import Optional


# ────────────────────────────── Research ──────────────────────────────
class StockQuote(BaseModel):
    ticker: str
    company_name: str
    current_price: float
    change_percent: float
    day_high: float
    day_low: float
    open_price: float
    previous_close: float
    volume: int


class FundamentalData(BaseModel):
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    roe: Optional[float] = None
    debt_equity: Optional[float] = None
    free_cash_flow: Optional[float] = None
    revenue_growth: Optional[float] = None
    eps_growth: Optional[float] = None
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None


class TechnicalData(BaseModel):
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    rsi_14: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    beta: Optional[float] = None
    atr: Optional[float] = None


class NewsSentiment(BaseModel):
    headline: str
    source: str
    url: str
    sentiment: Optional[float] = None
    published_at: str


class ResearchReport(BaseModel):
    ticker: str
    quote: StockQuote
    fundamentals: FundamentalData
    technicals: TechnicalData
    news: list[NewsSentiment]
    analyst_rating: Optional[str] = None
    composite_score: Optional[int] = None
    summary: Optional[str] = None
    fetched_at: str


# ────────────────────────────── Watchlist ──────────────────────────────
class WatchlistAddRequest(BaseModel):
    ticker: str
    category: str = "general"
    notes: Optional[str] = None


class WatchlistItem(BaseModel):
    id: int
    ticker: str
    category: str
    notes: Optional[str] = None
    added_at: str


class AlertCreateRequest(BaseModel):
    ticker: str
    condition_type: str  # price_above, price_below, rsi_oversold, volume_spike
    threshold: float
    operator: str = ">"


class AlertItem(BaseModel):
    id: int
    ticker: str
    condition_type: str
    threshold: float
    operator: str
    triggered: bool
    created_at: str


# ────────────────────────────── Journal ──────────────────────────────
class JournalParseRequest(BaseModel):
    message: str


class TradeEntryRequest(BaseModel):
    ticker: str
    direction: str = "LONG"
    entry_price: float
    shares: int
    strategy: Optional[str] = None
    setup_notes: Optional[str] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    mood: Optional[str] = None
    market_condition: Optional[str] = None


class TradeExitRequest(BaseModel):
    exit_price: float
    exit_reason: str = "Manual"
    fees: float = 0
    exit_notes: Optional[str] = None


class TradeRecord(BaseModel):
    id: int
    trade_id: str
    ticker: str
    direction: str
    entry_date: str
    entry_price: float
    shares: int
    strategy: Optional[str] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    risk_reward: Optional[str] = None
    mood: Optional[str] = None
    status: str
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    pnl_absolute: Optional[float] = None
    pnl_percent: Optional[float] = None
    created_at: str


# ────────────────────────────── Analytics ──────────────────────────────
class PerformanceStats(BaseModel):
    total_trades: int
    open_trades: int
    closed_trades: int
    win_count: int
    loss_count: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: Optional[float] = None
    expectancy: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    best_trade: Optional[TradeRecord] = None
    worst_trade: Optional[TradeRecord] = None


class StrategyBreakdown(BaseModel):
    strategy: str
    trades: int
    win_rate: float
    total_pnl: float


# ────────────────────────────── Notifications ──────────────────────────────
class WhatsAppRequest(BaseModel):
    message: str
    to: Optional[str] = None


class WhatsAppResponse(BaseModel):
    status: str
    detail: str
