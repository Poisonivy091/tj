import sqlite3
from app.config.settings import settings

DB_PATH = settings.DB_PATH


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            notes TEXT,
            added_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            condition_type TEXT NOT NULL,
            threshold REAL,
            operator TEXT DEFAULT '>',
            triggered INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            triggered_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id TEXT UNIQUE NOT NULL,
            ticker TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_date TEXT NOT NULL,
            entry_price REAL NOT NULL,
            shares INTEGER NOT NULL,
            strategy TEXT,
            setup_notes TEXT,
            stop_loss REAL,
            target_price REAL,
            risk_reward TEXT,
            position_size_pct REAL,
            mood TEXT,
            market_condition TEXT,
            raw_message TEXT,
            -- Exit fields (filled when trade is closed)
            exit_date TEXT,
            exit_price REAL,
            exit_reason TEXT,
            fees REAL DEFAULT 0,
            pnl_absolute REAL,
            pnl_percent REAL,
            exit_notes TEXT,
            status TEXT DEFAULT 'OPEN',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS daily_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            realized_pnl REAL DEFAULT 0,
            unrealized_pnl REAL DEFAULT 0,
            total_value REAL DEFAULT 0,
            open_positions INTEGER DEFAULT 0,
            trades_closed INTEGER DEFAULT 0,
            win_count INTEGER DEFAULT 0,
            loss_count INTEGER DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()
