#!/usr/bin/env python3
"""
alpacaGetPrice.py
Fetch the latest real-time trade price via Alpaca.
⚠ Always uses LIVE API keys, never paper (paper is delayed 15m).
Env vars required:
  ALPACA_LIVE_KEY_ID
  ALPACA_LIVE_SECRET_KEY
"""

import os, sys, json, argparse
from pathlib import Path
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest

BASE_DIR = Path(__file__).resolve().parent

def die(msg: str, code: int = 1):
    print(json.dumps({"ok": False, "error": msg}), flush=True)
    sys.exit(code)

def get_data_client():
    key = os.getenv("ALPACA_LIVE_KEY_ID")
    sec = os.getenv("ALPACA_LIVE_SECRET_KEY")
    if not key or not sec:
        die("Missing ALPACA_LIVE_KEY_ID / ALPACA_LIVE_SECRET_KEY in environment")
    try:
        return StockHistoricalDataClient(key, sec)
    except Exception as e:
        die(f"Failed to init StockHistoricalDataClient: {e}")

def main():
    ap = argparse.ArgumentParser(description="Get latest real-time trade price via Alpaca")
    ap.add_argument("--symbol", required=True, help="Ticker symbol, e.g. SPY")
    args = ap.parse_args()

    client = get_data_client()

    try:
        rq = StockLatestTradeRequest(symbol_or_symbols=args.symbol.upper())
        latest = client.get_stock_latest_trade(rq)
        trade = latest[args.symbol.upper()]
        out = {
            "ok": True,
            "symbol": args.symbol.upper(),
            "price": float(trade.price),
            "ts": str(trade.timestamp) if hasattr(trade, "timestamp") else None
        }
        print(json.dumps(out), flush=True)
    except Exception as e:
        die(f"Error fetching latest trade for {args.symbol}: {e}")

if __name__ == "__main__":
    main()
