#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path

import krakenex
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent / ".env"
load_dotenv(ENV_PATH)


def die(message: str, code: int = 1):
    print(json.dumps({"ok": False, "error": message}), flush=True)
    sys.exit(code)


def main():
    key = os.getenv("KRAKEN_API_KEY") or os.getenv("API_KEY")
    secret = os.getenv("KRAKEN_API_SECRET") or os.getenv("API_SECRET")
    if not key or not secret:
        die("Missing Kraken API credentials in environment")

    api = krakenex.API(key=key, secret=secret)
    response = api.query_private("Balance")
    if response.get("error"):
        die(f"Kraken balance error: {response['error']}")

    print(json.dumps({"ok": True, "balances": response.get("result", {})}), flush=True)


if __name__ == "__main__":
    main()
