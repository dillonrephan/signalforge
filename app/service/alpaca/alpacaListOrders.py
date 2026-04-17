#!/usr/bin/env python3
"""
alpacaListOrders.py
List orders with optional filters.

Usage examples:
  python alpacaListOrders.py
  python alpacaListOrders.py --status all --limit 100
  python alpacaListOrders.py --status closed --symbol SPY
"""

import os, sys, json, argparse
from pathlib import Path
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import OrderSide, OrderType

# Note: In alpaca-py, GetOrdersRequest.status type may vary by version.
# If needed, we'll pass strings and normalize client-side.

# ---------- load .env from parent directory ----------
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"
load_dotenv(ENV_PATH)

def die(msg: str, code: int = 1):
    print(json.dumps({"ok": False, "error": msg}, default=str), flush=True)
    sys.exit(code)

def get_trading_client():
    mode = os.getenv("ALPACA_MODE", "paper").lower()
    if mode == "live":
        key, sec, paper = os.getenv("ALPACA_LIVE_KEY_ID"), os.getenv("ALPACA_LIVE_SECRET_KEY"), False
    else:
        key, sec, paper = os.getenv("ALPACA_PAPER_KEY_ID"), os.getenv("ALPACA_PAPER_SECRET_KEY"), True
    if not key or not sec:
        die(f"Missing API keys for mode='{mode}'. Check {ENV_PATH}.")
    try:
        return TradingClient(key, sec, paper=paper), mode
    except Exception as e:
        die(f"Failed to init TradingClient: {e}")

def normalize_order(o):
    return {
        "id": str(getattr(o, "id", "")),
        "symbol": getattr(o, "symbol", None),
        "qty": float(getattr(o, "qty", 0.0)) if getattr(o, "qty", None) is not None else None,
        "filled_qty": float(getattr(o, "filled_qty", 0.0)) if getattr(o, "filled_qty", None) is not None else None,
        "side": getattr(o, "side", None),
        "type": getattr(o, "type", None),
        "status": getattr(o, "status", None),
        "limit_price": float(getattr(o, "limit_price", 0.0)) if getattr(o, "limit_price", None) is not None else None,
        "stop_price": float(getattr(o, "stop_price", 0.0)) if getattr(o, "stop_price", None) is not None else None,
        "submitted_at": getattr(o, "submitted_at", None),
        "filled_at": getattr(o, "filled_at", None),
        "expired_at": getattr(o, "expired_at", None),
        "canceled_at": getattr(o, "canceled_at", None),
        "replaced_by": str(getattr(o, "replaced_by", "")) if getattr(o, "replaced_by", None) else None,
        "replaces": str(getattr(o, "replaces", "")) if getattr(o, "replaces", None) else None,
    }

def main():
    ap = argparse.ArgumentParser(description="List Alpaca orders as JSON")
    ap.add_argument("--status", choices=["open", "closed", "all"], default="open",
                    help="Order status to fetch (default: open)")
    ap.add_argument("--limit", type=int, default=50, help="Max number of orders to return")
    ap.add_argument("--symbol", help="Filter results to this symbol (client-side)")
    args = ap.parse_args()

    client, mode = get_trading_client()

    # Build request
    # Many versions of alpaca-py accept status as str ("open"/"closed"/"all") in GetOrdersRequest.
    # If your version requires an enum, it will still work with strings or you can map here.
    request = GetOrdersRequest(status=args.status, limit=args.limit)

    try:
        orders = client.get_orders(request)
        # Optional client-side symbol filter (SDK's symbols= list could also be used)
        if args.symbol:
            orders = [o for o in orders if getattr(o, "symbol", None) == args.symbol]

        data = [normalize_order(o) for o in orders]
        print(json.dumps({"ok": True, "mode": mode, "count": len(data), "orders": data}, default=str), flush=True)
    except Exception as e:
        die(f"Error listing orders: {e}")

if __name__ == "__main__":
    main()
