from pydantic import BaseModel
from typing import Optional


# ────────────────────────────── Research ──────────────────────────────
class PriceData(BaseModel):
    """All price points: regular, pre-market, post-market."""
    regular_market_price: float
    previous_close: float
    open_price: float
    day_high: float
    day_low: float
    change_amount: float
    change_percent: float
    # Post-market (after hours)
    post_market_price: Optional[float] = None
    post_market_change: Optional[float] = None
    post_market_change_percent: Optional[float] = None
    # Pre-market
    pre_market_price: Optional[float] = None
    pre_market_change: Optional[float] = None
    pre_market_change_percent: Optional[float] = None


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
    price_data: PriceData


class FundamentalData(BaseModel):
    pe_ratio: Optional[float] = None
    peg_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    debt_equity: Optional[float] = None
    current_ratio: Optional[float] = None
    free_cash_flow: Optional[float] = None
    operating_margin: Optional[float] = None
    profit_margin: Optional[float] = None
    revenue_growth: Optional[float] = None
    eps_growth: Optional[float] = None
    eps_ttm: Optional[float] = None
    dividend_yield: Optional[float] = None
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    shares_outstanding: Optional[float] = None
    short_percent_of_float: Optional[float] = None
    earnings_date: Optional[str] = None


class TechnicalData(BaseModel):
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    rsi_14: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    beta: Optional[float] = None
    atr: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None


class NewsSentiment(BaseModel):
    headline: str
    source: str
    url: str
    sentiment: Optional[float] = None
    published_at: str


class SECFiling(BaseModel):
    form_type: str
    filed_at: str
    description: str
    url: str


class InsiderTrade(BaseModel):
    filed_at: str
    filer: str
    form_type: str


class AnalystPriceTarget(BaseModel):
    """Consensus price targets from analysts/firms."""
    target_high: Optional[float] = None
    target_low: Optional[float] = None
    target_mean: Optional[float] = None
    target_median: Optional[float] = None
    number_of_analysts: Optional[int] = None
    last_updated: Optional[str] = None


class AnalystAction(BaseModel):
    """Individual analyst upgrade/downgrade action."""
    firm: str
    action: str  # upgrade, downgrade, initiated, reiterated
    from_grade: Optional[str] = None
    to_grade: Optional[str] = None
    date: str


class EarningsSurprise(BaseModel):
    """Quarterly earnings actual vs estimate."""
    period: str
    actual: Optional[float] = None
    estimate: Optional[float] = None
    surprise: Optional[float] = None
    surprise_percent: Optional[float] = None


class DataSources(BaseModel):
    """Track which sources successfully provided data."""
    yahoo_finance: bool = False
    finnhub: bool = False
    alpha_vantage: bool = False
    newsapi: bool = False
    sec_edgar: bool = False


class ResearchReport(BaseModel):
    ticker: str
    quote: StockQuote
    fundamentals: FundamentalData
    technicals: TechnicalData
    news: list[NewsSentiment]
    sec_filings: list[SECFiling] = []
    insider_trades: list[InsiderTrade] = []
    price_targets: Optional[AnalystPriceTarget] = None
    analyst_actions: list[AnalystAction] = []
    earnings_history: list[EarningsSurprise] = []
    analyst_rating: Optional[str] = None
    composite_score: Optional[int] = None
    summary: Optional[str] = None
    data_sources: DataSources = DataSources()
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


# ────────────────────────────── AI Trader ──────────────────────────────

class BreakoutSignal(BaseModel):
    """A single detected technical breakout condition."""
    signal_type: str          # e.g. "52W_HIGH_BREAK", "GOLDEN_CROSS", "RSI_REVERSAL"
    description: str
    severity: str             # "strong", "moderate", "weak"
    triggered_at: Optional[str] = None


class AITradingSignal(BaseModel):
    """Full AI-generated trade signal for a ticker."""
    id: Optional[int] = None
    ticker: str
    fund_style: str           # ark | blackrock | momentum
    action: str               # BUY | SELL | HOLD | WATCH
    conviction: int           # 1-10 (10 = highest conviction)
    entry_price: Optional[float] = None
    entry_range_low: Optional[float] = None
    entry_range_high: Optional[float] = None
    stop_loss: Optional[float] = None
    price_target: Optional[float] = None
    target_horizon: Optional[str] = None   # e.g. "3-6 months"
    position_size_pct: Optional[float] = None  # % of portfolio suggested
    reasoning: str
    key_catalysts: list[str] = []
    key_risks: list[str] = []
    breakout_signals: list[BreakoutSignal] = []
    composite_score: Optional[int] = None
    current_price: Optional[float] = None
    generated_at: str


class WatchlistScanRequest(BaseModel):
    fund_style: str = "ark"   # ark | blackrock | momentum
    min_conviction: int = 6   # Only return signals with conviction >= this


class WatchlistScanResult(BaseModel):
    scanned: int
    signals_generated: int
    buy_signals: list[AITradingSignal]
    sell_signals: list[AITradingSignal]
    watch_signals: list[AITradingSignal]
    scan_duration_seconds: Optional[float] = None
    scanned_at: str


class AIPortfolioPosition(BaseModel):
    """An AI-managed position in the virtual portfolio."""
    id: Optional[int] = None
    ticker: str
    direction: str            # LONG | SHORT
    shares: float
    entry_price: float
    current_price: Optional[float] = None
    stop_loss: Optional[float] = None
    price_target: Optional[float] = None
    fund_style: str
    conviction: int
    reasoning: str
    status: str = "OPEN"      # OPEN | CLOSED
    pnl_absolute: Optional[float] = None
    pnl_percent: Optional[float] = None
    opened_at: str
    closed_at: Optional[str] = None


class AIPortfolioSummary(BaseModel):
    positions: list[AIPortfolioPosition]
    total_positions: int
    open_positions: int
    total_unrealized_pnl: float
    style: str
    last_updated: str


class ExecuteTradeRequest(BaseModel):
    """Ask AI to decide & record a trade based on its latest signal."""
    ticker: str
    fund_style: str = "ark"
    portfolio_value: float = 100000  # virtual portfolio size in USD
    force_action: Optional[str] = None  # override: BUY | SELL | HOLD


class StyleConfigRequest(BaseModel):
    fund_style: str  # ark | blackrock | momentum
    portfolio_value: float = 100000
