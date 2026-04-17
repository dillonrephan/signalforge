#!/usr/bin/env python3

import argparse
import json
import sys

import requests

PAIR_MAP = {
    "BTC/USD": "XXBTZUSD",
    "ETH/USD": "XETHZUSD",
}


def die(message: str, code: int = 1):
    print(json.dumps({"ok": False, "error": message}), flush=True)
    sys.exit(code)


def main():
    ap = argparse.ArgumentParser(description="Fetch the current Kraken price")
    ap.add_argument("--symbol", required=True, help="Supported: BTC/USD, ETH/USD")
    args = ap.parse_args()

    symbol = args.symbol.upper()
    pair = PAIR_MAP.get(symbol)
    if not pair:
        die(f"Unsupported Kraken symbol: {symbol}")

    try:
        response = requests.get("https://api.kraken.com/0/public/Ticker", params={"pair": pair}, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        die(f"Kraken request failed: {exc}")

    if data.get("error"):
        die(f"Kraken ticker error: {data['error']}")

    try:
        price = float(data["result"][pair]["c"][0])
    except (KeyError, ValueError, TypeError):
        die("Unexpected Kraken ticker response")

    print(json.dumps({"ok": True, "symbol": symbol, "price": price}), flush=True)


if __name__ == "__main__":
    main()
