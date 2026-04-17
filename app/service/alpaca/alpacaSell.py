#!/usr/bin/env python3
"""
alpacaSell.py
Sell shares via Alpaca. Works in paper or live mode based on env:
  ALPACA_MODE=paper|live
Requires keys in env:
  - paper: ALPACA_PAPER_KEY_ID, ALPACA_PAPER_SECRET_KEY
  - live : ALPACA_LIVE_KEY_ID,  ALPACA_LIVE_SECRET_KEY
"""

import os, sys, json, argparse
from pathlib import Path
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import OrderRequest
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce

# ---------- load .env from parent directory ----------
# If script is at .../app/alpaca/alpacaSell.py, this points to .../app/.env
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"
load_dotenv(ENV_PATH)

def die(msg: str, code: int = 1):
    print(json.dumps({"ok": False, "error": msg}, default=str), flush=True)
    sys.exit(code)

def get_trading_client():
    mode = os.getenv("ALPACA_MODE", "paper").lower()
    if mode == "live":
        key = os.getenv("ALPACA_LIVE_KEY_ID")
        sec = os.getenv("ALPACA_LIVE_SECRET_KEY")
        paper = False
    else:
        key = os.getenv("ALPACA_PAPER_KEY_ID")
        sec = os.getenv("ALPACA_PAPER_SECRET_KEY")
        paper = True

    if not key or not sec:
        die(f"Missing API keys for mode='{mode}'. Check environment variables at {ENV_PATH}.")

    try:
        return TradingClient(key, sec, paper=paper), mode
    except Exception as e:
        die(f"Failed to init TradingClient: {e}")

def main():
    ap = argparse.ArgumentParser(description="Submit a SELL order via Alpaca")
    ap.add_argument("--symbol", required=True, help="Ticker symbol, e.g. SPY")
    ap.add_argument("--qty", required=True, type=float, help="Quantity to sell (shares)")
    ap.add_argument("--limit", type=float, default=None, help="Limit price (omit for market)")
    ap.add_argument("--tif", default="day", choices=["day","gtc","opg","cls","ioc","fok"],
                    help="Time in force (default: day)")
    ap.add_argument("--extended-hours", action="store_true",
                    help="Allow order during extended hours (for eligible types)")
    args = ap.parse_args()

    trading, mode = get_trading_client()

    order_type = OrderType.LIMIT if args.limit is not None else OrderType.MARKET
    # Correct enum mapping (e.g., "day" -> TimeInForce.DAY)
    tif = TimeInForce[args.tif.upper()]

    req = OrderRequest(
        symbol=args.symbol,
        qty=str(args.qty),
        side=OrderSide.SELL,
        type=order_type,
        time_in_force=tif,
        limit_price=str(args.limit) if args.limit is not None else None,
        extended_hours=bool(args.extended_hours),
    )

    try:
        order = trading.submit_order(req)
        out = {
            "ok": True,
            "mode": mode,
            "action": "sell",
            "symbol": args.symbol,
            "qty": float(args.qty),
            "type": "limit" if args.limit is not None else "market",
            "limit": float(args.limit) if args.limit is not None else None,
            "time_in_force": args.tif,
            "extended_hours": bool(args.extended_hours),
            "id": str(getattr(order, "id", "")),            # UUID -> str
            "status": getattr(order, "status", None),
            "submitted_at": getattr(order, "submitted_at", None),  # datetime handled by default=str
        }
        print(json.dumps(out, default=str), flush=True)
    except Exception as e:
        die(f"Error placing sell order: {e}")

if __name__ == "__main__":
    main()
