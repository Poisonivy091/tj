import re


def parse_trade_message(message: str) -> dict:
    """Parse natural-language trade entries.

    Examples:
        "Bought 50 NVDA at 875 stop 850 target 920"
        "Sold 100 AAPL @ 185.5 sl 180 tp 195"
        "Long 200 TSLA at 245 stop-loss 238 take-profit 260"
        "Short 30 META at 500 stop 515 target 470"
    """
    msg = message.strip()

    # Detect action
    action_match = re.match(r"(bought|sold|buy|sell|long|short)", msg, re.IGNORECASE)
    if not action_match:
        raise ValueError(f"Could not detect trade action (buy/sell/long/short) in: {msg}")
    raw_action = action_match.group(1).lower()

    if raw_action in ("bought", "buy", "long"):
        action = "BUY"
        direction = "LONG"
    else:
        action = "SELL"
        direction = "SHORT"

    # Quantity and ticker
    qty_match = re.search(r"(\d+)\s+([A-Za-z]{1,5})", msg[action_match.end():])
    if not qty_match:
        raise ValueError(f"Could not detect quantity and ticker in: {msg}")
    quantity = int(qty_match.group(1))
    ticker = qty_match.group(2).upper()

    # Price
    price_match = re.search(r"(?:at|@)\s*\$?([\d,.]+)", msg, re.IGNORECASE)
    if not price_match:
        raise ValueError(f"Could not detect price in: {msg}")
    price = float(price_match.group(1).replace(",", ""))

    # Stop loss (optional)
    stop_loss = None
    stop_match = re.search(r"(?:stop|sl|stop[\s-]?loss)\s*\$?([\d,.]+)", msg, re.IGNORECASE)
    if stop_match:
        stop_loss = float(stop_match.group(1).replace(",", ""))

    # Target (optional)
    target = None
    target_match = re.search(r"(?:target|tp|take[\s-]?profit)\s*\$?([\d,.]+)", msg, re.IGNORECASE)
    if target_match:
        target = float(target_match.group(1).replace(",", ""))

    # Strategy detection (optional keywords)
    strategy = None
    strategy_keywords = {
        "breakout": "Breakout",
        "pullback": "Pullback",
        "momentum": "Momentum",
        "swing": "Swing",
        "scalp": "Scalp",
        "earnings": "Earnings Play",
        "dip": "Buy the Dip",
        "gap": "Gap Play",
    }
    msg_lower = msg.lower()
    for kw, name in strategy_keywords.items():
        if kw in msg_lower:
            strategy = name
            break

    # Risk/reward calculation
    risk_reward = None
    if stop_loss and target and price:
        risk = abs(price - stop_loss)
        reward = abs(target - price)
        if risk > 0:
            risk_reward = f"1:{round(reward / risk, 1)}"

    return {
        "action": action,
        "direction": direction,
        "ticker": ticker,
        "quantity": quantity,
        "price": price,
        "stop_loss": stop_loss,
        "target": target,
        "strategy": strategy,
        "risk_reward": risk_reward,
    }
