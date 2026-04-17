#!/usr/bin/env python3

import argparse
import json
import os
import sys
from pathlib import Path

import krakenex
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"
load_dotenv(ENV_PATH)

PAIR_MAP = {
    "BTC/USD": {"ticker": "XXBTZUSD", "order": "XBTUSD", "asset": "XXBT", "price_decimals": 1},
    "ETH/USD": {"ticker": "XETHZUSD", "order": "ETHUSD", "asset": "XETH", "price_decimals": 2},
}


def die(message: str, code: int = 1):
    print(json.dumps({"ok": False, "error": message}), flush=True)
    sys.exit(code)


def get_api() -> krakenex.API:
    key = os.getenv("KRAKEN_API_KEY") or os.getenv("API_KEY")
    secret = os.getenv("KRAKEN_API_SECRET") or os.getenv("API_SECRET")
    if not key or not secret:
        die("Missing Kraken API credentials in environment")
    return krakenex.API(key, secret)


def get_pair(symbol: str) -> dict:
    pair = PAIR_MAP.get(symbol.upper())
    if not pair:
        die(f"Unsupported Kraken symbol: {symbol}")
    return pair


def get_current_price(api: krakenex.API, pair: dict) -> float:
    response = api.query_public("Ticker", {"pair": pair["ticker"]})
    if response.get("error"):
        die(f"Kraken ticker error: {response['error']}")
    return float(response["result"][pair["ticker"]]["c"][0])


def main():
    ap = argparse.ArgumentParser(description="Submit a BUY order via Kraken")
    ap.add_argument("--symbol", required=True, help="Supported: BTC/USD, ETH/USD")
    ap.add_argument("--qty", required=True, type=float, help="Quantity to buy")
    ap.add_argument("--limit", type=float, default=None, help="Limit price")
    args = ap.parse_args()

    api = get_api()
    pair = get_pair(args.symbol)
    limit_price = args.limit
    if limit_price is None:
        current = get_current_price(api, pair)
        limit_price = round(current * 1.001, pair["price_decimals"])

    order_data = {
        "pair": pair["order"],
        "type": "buy",
        "ordertype": "limit",
        "price": str(limit_price),
        "volume": str(args.qty),
    }
    response = api.query_private("AddOrder", order_data)
    if response.get("error"):
        die(f"Kraken order error: {response['error']}")

    print(json.dumps({
        "ok": True,
        "status": "submitted",
        "symbol": args.symbol.upper(),
        "qty": args.qty,
        "limit": float(limit_price),
        "result": response.get("result", {}),
    }), flush=True)


if __name__ == "__main__":
    main()
