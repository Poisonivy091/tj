from app.database.db import get_db
from app.models.schemas import PerformanceStats, TradeRecord, StrategyBreakdown


def _row_to_trade(row) -> TradeRecord:
    return TradeRecord(
        id=row["id"],
        trade_id=row["trade_id"],
        ticker=row["ticker"],
        direction=row["direction"],
        entry_date=row["entry_date"],
        entry_price=row["entry_price"],
        shares=row["shares"],
        strategy=row["strategy"],
        stop_loss=row["stop_loss"],
        target_price=row["target_price"],
        risk_reward=row["risk_reward"],
        mood=row["mood"],
        status=row["status"],
        exit_date=row["exit_date"],
        exit_price=row["exit_price"],
        pnl_absolute=row["pnl_absolute"],
        pnl_percent=row["pnl_percent"],
        created_at=row["created_at"],
    )


def get_performance_stats() -> PerformanceStats:
    db = get_db()
    try:
        all_trades = db.execute("SELECT * FROM trades ORDER BY created_at").fetchall()
        closed = [t for t in all_trades if t["status"] == "CLOSED"]
        open_trades = [t for t in all_trades if t["status"] == "OPEN"]

        wins = [t for t in closed if (t["pnl_absolute"] or 0) > 0]
        losses = [t for t in closed if (t["pnl_absolute"] or 0) <= 0]

        total_pnl = sum(t["pnl_absolute"] or 0 for t in closed)
        avg_win = (sum(t["pnl_absolute"] or 0 for t in wins) / len(wins)) if wins else 0
        avg_loss = (sum(t["pnl_absolute"] or 0 for t in losses) / len(losses)) if losses else 0
        win_rate = (len(wins) / len(closed) * 100) if closed else 0

        gross_profit = sum(t["pnl_absolute"] or 0 for t in wins)
        gross_loss = abs(sum(t["pnl_absolute"] or 0 for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

        expectancy = (
            (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)
        ) if closed else 0

        # Max consecutive wins/losses
        max_cons_wins = max_cons_losses = cons_wins = cons_losses = 0
        for t in closed:
            if (t["pnl_absolute"] or 0) > 0:
                cons_wins += 1
                cons_losses = 0
            else:
                cons_losses += 1
                cons_wins = 0
            max_cons_wins = max(max_cons_wins, cons_wins)
            max_cons_losses = max(max_cons_losses, cons_losses)

        best = max(closed, key=lambda t: t["pnl_absolute"] or 0) if closed else None
        worst = min(closed, key=lambda t: t["pnl_absolute"] or 0) if closed else None

        return PerformanceStats(
            total_trades=len(all_trades),
            open_trades=len(open_trades),
            closed_trades=len(closed),
            win_count=len(wins),
            loss_count=len(losses),
            win_rate=round(win_rate, 2),
            total_pnl=round(total_pnl, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            profit_factor=round(profit_factor, 2) if profit_factor else None,
            expectancy=round(expectancy, 2),
            max_consecutive_wins=max_cons_wins,
            max_consecutive_losses=max_cons_losses,
            best_trade=_row_to_trade(best) if best else None,
            worst_trade=_row_to_trade(worst) if worst else None,
        )
    finally:
        db.close()


def get_strategy_breakdown() -> list[StrategyBreakdown]:
    db = get_db()
    try:
        rows = db.execute("""
            SELECT strategy,
                   COUNT(*) as cnt,
                   SUM(CASE WHEN pnl_absolute > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(COALESCE(pnl_absolute, 0)) as total_pnl
            FROM trades
            WHERE status = 'CLOSED' AND strategy IS NOT NULL
            GROUP BY strategy
            ORDER BY total_pnl DESC
        """).fetchall()

        return [
            StrategyBreakdown(
                strategy=r["strategy"],
                trades=r["cnt"],
                win_rate=round(r["wins"] / r["cnt"] * 100, 2) if r["cnt"] else 0,
                total_pnl=round(r["total_pnl"], 2),
            )
            for r in rows
        ]
    finally:
        db.close()
