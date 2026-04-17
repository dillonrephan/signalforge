#!/usr/bin/env python3
"""
alpacaCancel.py
Cancel a single order by id or cancel all open orders.

Usage examples:
  # cancel a single order
  python alpacaCancel.py --id <order_id>

  # cancel ALL open orders
  python alpacaCancel.py --all

  # cancel ALL open orders for a specific symbol
  python alpacaCancel.py --all --symbol SPY
"""

import os, sys, json, argparse
from pathlib import Path
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest

# ---------- load .env from parent directory ----------
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"    # scripts in .../app/alpaca -> .env at .../app/.env
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

def cancel_by_id(client: TradingClient, order_id: str):
    try:
        client.cancel_order_by_id(order_id)
        print(json.dumps({"ok": True, "action": "cancel_by_id", "id": order_id}, default=str), flush=True)
    except Exception as e:
        die(f"Error canceling order {order_id}: {e}")

def cancel_all(client: TradingClient, symbol: str | None):
    try:
        if symbol:
            # Cancel only open orders for this symbol
            # Fetch open orders then cancel individually
            req = GetOrdersRequest()  # open by default in latest SDK; if not, it's fine to still filter client-side
            orders = client.get_orders(req)
            canceled = []
            for o in orders:
                if getattr(o, "symbol", None) == symbol:
                    try:
                        client.cancel_order_by_id(str(getattr(o, "id", "")))
                        canceled.append(str(getattr(o, "id", "")))
                    except Exception as ie:
                        # include failures but don't abort the whole batch
                        canceled.append({"id": str(getattr(o, "id", "")), "error": str(ie)})
            print(json.dumps({"ok": True, "action": "cancel_all", "symbol": symbol, "canceled": canceled}, default=str), flush=True)
        else:
            # Cancel all open orders (SDK endpoint)
            client.cancel_orders()
            print(json.dumps({"ok": True, "action": "cancel_all"}, default=str), flush=True)
    except Exception as e:
        die(f"Error canceling orders: {e}")

def main():
    ap = argparse.ArgumentParser(description="Cancel Alpaca orders")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", help="Order ID to cancel")
    g.add_argument("--all", action="store_true", help="Cancel all open orders")
    ap.add_argument("--symbol", help="When used with --all, limit to this symbol")
    args = ap.parse_args()

    client, mode = get_trading_client()

    if args.id:
        cancel_by_id(client, args.id)
    else:
        cancel_all(client, args.symbol)

if __name__ == "__main__":
    main()
