#!/usr/bin/env python3
"""
alpacaGetBalance.py
Return account balances via Alpaca Trading API.
"""

import os, sys, json, argparse
from pathlib import Path
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

# ---------- load .env from your specified location ----------
BASE_DIR = Path(__file__).resolve().parent       # .../tradingBot/alpaca
ENV_PATH = BASE_DIR.parent / ".env"              # .../tradingBot/.env
# OR, if you’re keeping it specifically in .../tradingBot/app/.env:
# ENV_PATH = BASE_DIR.parent / "app" / ".env"

load_dotenv(ENV_PATH)


def die(msg: str, code: int = 1):
    print(json.dumps({"ok": False, "error": msg}, default=str), flush=True)
    sys.exit(code)

def get_mode(cli_mode: str | None) -> str:
    if cli_mode:
        return cli_mode.lower()
    return os.getenv("ALPACA_MODE", "paper").lower()

def get_client(mode: str) -> TradingClient:
    if mode == "live":
        key, sec, paper = os.getenv("ALPACA_LIVE_KEY_ID"), os.getenv("ALPACA_LIVE_SECRET_KEY"), False
    else:
        key, sec, paper = os.getenv("ALPACA_PAPER_KEY_ID"), os.getenv("ALPACA_PAPER_SECRET_KEY"), True

    if not key or not sec:
        die(f"Missing API keys for mode='{mode}'. Check {ENV_PATH} or environment variables.")
    try:
        return TradingClient(key, sec, paper=paper)
    except Exception as e:
        die(f"Failed to init TradingClient: {e}")

def main():
    ap = argparse.ArgumentParser(description="Return Alpaca account balances as JSON")
    ap.add_argument("--mode", choices=["paper","live"], help="Override ALPACA_MODE")
    args = ap.parse_args()

    mode = get_mode(args.mode)
    client = get_client(mode)

    try:
        acct = client.get_account()
        out = {
            "ok": True,
            "mode": mode,
            "account_id": str(getattr(acct, "id", "")),  # UUID -> str
            "currency": "USD",
            "cash": float(getattr(acct, "cash", 0.0)),
            "buying_power": float(getattr(acct, "buying_power", 0.0)),
            "portfolio_value": float(getattr(acct, "portfolio_value", 0.0)),
            "equity": float(getattr(acct, "equity", 0.0)),
            "multiplier": getattr(acct, "multiplier", None),
            "status": getattr(acct, "status", None),
            "pattern_day_trader": bool(getattr(acct, "pattern_day_trader", False)),
            "trade_suspended_by_user": bool(getattr(acct, "trade_suspended_by_user", False)),
        }
        print(json.dumps(out, default=str), flush=True)
    except Exception as e:
        die(f"Error fetching account: {e}")

if __name__ == "__main__":
    main()
