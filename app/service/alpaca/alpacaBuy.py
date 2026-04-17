#!/usr/bin/env python3
"""
alpacaBuy.py
Buy shares via Alpaca. Works in paper or live mode based on env:
  ALPACA_MODE=paper|live
Requires keys in env:
  - paper: ALPACA_PAPER_KEY_ID, ALPACA_PAPER_SECRET_KEY
  - live : ALPACA_LIVE_KEY_ID,  ALPACA_LIVE_SECRET_KEY
"""

import os, sys, json, argparse
from pathlib import Path
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import OrderRequest
from alpaca.trading.enums import OrderSide, OrderType, TimeInForce
from dotenv import load_dotenv

# ---------- load .env from your specified location ----------
BASE_DIR = Path(__file__).resolve().parent        # .../app/alpaca
ENV_PATH = BASE_DIR.parent / ".env"               # .../app/.env  (adjust if needed)
# If your .env is actually at .../tradingBot/app/.env and scripts are under .../tradingBot/app/alpaca, this is correct.
load_dotenv(ENV_PATH)

def die(msg: str, code: int = 1):
    print(json.dumps({"ok": False, "error": msg}), flush=True)
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
        die(f"Missing API keys for mode='{mode}'. Check environment variables.")

    try:
        return TradingClient(key, sec, paper=paper), mode
    except Exception as e:
        die(f"Failed to init TradingClient: {e}")

def main():
    ap = argparse.ArgumentParser(description="Submit a BUY order via Alpaca")
    ap.add_argument("--symbol", required=True, help="Ticker symbol, e.g. SPY")
    ap.add_argument("--qty", required=True, type=float, help="Quantity to buy (shares)")
    ap.add_argument("--limit", type=float, default=None, help="Limit price (omit for market)")
    ap.add_argument("--tif", default="day", choices=["day","gtc","opg","cls","ioc","fok"],
                    help="Time in force (default: day)")
    ap.add_argument("--extended-hours", action="store_true",
                    help="Allow order during extended hours (for eligible types)")
    args = ap.parse_args()

    trading, mode = get_trading_client()

    order_type = OrderType.LIMIT if args.limit is not None else OrderType.MARKET
    # FIXED: map lowercase choice to enum member
    tif = TimeInForce[args.tif.upper()]

    req = OrderRequest(
        symbol=args.symbol,
        qty=str(args.qty),
        side=OrderSide.BUY,
        type=order_type,
        time_in_force=tif,
        limit_price=str(args.limit) if args.limit is not None else None,
        extended_hours=bool(args.extended_hours),
    )

    try:
        order = trading.submit_order(req)
        # Normalize response for the caller (main.py)
        out = {
            "ok": True,
            "mode": mode,
            "symbol": args.symbol,
            "qty": float(args.qty),
            "type": "limit" if args.limit is not None else "market",
            "limit": float(args.limit) if args.limit is not None else None,
            "time_in_force": args.tif,
            "extended_hours": bool(args.extended_hours),
            "id": str(getattr(order, "id", "")),           # UUID -> str
            "status": getattr(order, "status", None),
            "submitted_at": getattr(order, "submitted_at", None)  # datetime handled by default=str
        }
        print(json.dumps(out, default=str), flush=True)    # <— key change
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Error placing buy order: {e}"}, default=str), flush=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
