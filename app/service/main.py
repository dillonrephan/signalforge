#!/usr/bin/env python3
# main.py — unified broker router for TradingView webhooks with structured JSON logging

import json
import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, jsonify, request


BASE_DIR = Path(__file__).resolve().parent
PY_BIN = sys.executable

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "broker.log"
EXPOSE_CONFIG = os.getenv("EXPOSE_CONFIG", "false").lower() == "true"
MAX_REQUEST_BYTES = int(os.getenv("MAX_REQUEST_BYTES", "16384"))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize_payload(payload: dict) -> dict:
    try:
        sanitized = dict(payload)
    except Exception:
        return {"_payload": "non-serializable"}

    for key in ("secret", "api_key", "apikey", "token", "password", "key", "authorization", "Authorization"):
        if key in sanitized:
            sanitized[key] = "***"
    return sanitized


def event_identity(payload: dict) -> tuple[str, str]:
    for key in ("event_id", "alert_id", "alertId", "alertID", "id"):
        value = payload.get(key)
        if value not in (None, ""):
            return str(value), "tradingview"
    return uuid.uuid4().hex, "manual"


class EventLogger(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra["event_id"] = self.extra.get("event_id")
        kwargs["extra"] = extra
        return msg, kwargs


def make_event_logger(event_id: str) -> EventLogger:
    return EventLogger(logging.getLogger("broker"), {"event_id": event_id})


def log_event(evlog: EventLogger, event: str, **fields):
    record = {"ts": utcnow(), "event": event, "event_id": evlog.extra.get("event_id")}
    record.update(fields)
    evlog.info(json.dumps(record, default=str))


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=5, encoding="utf-8"),
    ],
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES

# Defaults & safety
DEFAULT_BROKER_PROFILE = os.getenv("BROKER_PROFILE", "alpaca_paper").lower()
ALLOW_LIVE = os.getenv("ALLOW_LIVE", "false").lower() == "true"
PRICE_TOLERANCE = float(os.getenv("PRICE_TOLERANCE", "0.50"))

# All paths are anchored to BASE_DIR. Child scripts must accept:
#   --symbol <sym> [--qty <n>] [--limit <px>]
SCRIPT_MAP = {
    "kraken": {
        "buy": str(BASE_DIR / "kraken" / "buy.py"),
        "sell": str(BASE_DIR / "kraken" / "sell.py"),
        "price": str(BASE_DIR / "kraken" / "getPrice.py"),
        "allowed": {"BTC/USD", "ETH/USD"},
        "env": {},
    },
    "alpaca_paper": {
        "buy": str(BASE_DIR / "alpaca" / "alpacaBuy.py"),
        "sell": str(BASE_DIR / "alpaca" / "alpacaSell.py"),
        "price": str(BASE_DIR / "alpaca" / "alpacaGetPrice.py"),
        "allowed": {"SPY", "AAPL"},
        "env": {"ALPACA_MODE": "paper"},
    },
    "alpaca_live": {
        "buy": str(BASE_DIR / "alpaca" / "alpacaBuy.py"),
        "sell": str(BASE_DIR / "alpaca" / "alpacaSell.py"),
        "price": str(BASE_DIR / "alpaca" / "alpacaGetPrice.py"),
        "allowed": {"SPY", "AAPL"},
        "env": {"ALPACA_MODE": "live"},
    },
}

ASSET_MAP = {
    "kraken": {"BTCUSD": "BTC/USD", "ETHUSD": "ETH/USD"},
    "alpaca_paper": {"SPY": "SPY", "AAPL": "AAPL"},
    "alpaca_live": {"SPY": "SPY", "AAPL": "AAPL"},
}


def ensure_files(profile: str):
    entry = SCRIPT_MAP[profile]
    for key in ("buy", "sell", "price"):
        path = Path(entry[key])
        if not path.is_file():
            raise FileNotFoundError(f"Missing script for {profile}:{key} -> {path}")


def select_profile(payload: dict, evlog: EventLogger) -> str:
    requested = (payload.get("broker_profile") or DEFAULT_BROKER_PROFILE).lower()
    if requested not in SCRIPT_MAP:
        log_event(evlog, "profile_fallback", requested=requested, fallback=DEFAULT_BROKER_PROFILE)
        requested = DEFAULT_BROKER_PROFILE
    if requested == "alpaca_live" and not ALLOW_LIVE:
        log_event(evlog, "profile_blocked_live", requested=requested, fallback=DEFAULT_BROKER_PROFILE)
        requested = DEFAULT_BROKER_PROFILE
    ensure_files(requested)
    return requested


def norm_symbol(profile: str, symbol: str) -> str:
    return ASSET_MAP.get(profile, {}).get(symbol, symbol)


def run_script(pyfile: str, args: list[str], extra_env: dict | None, evlog: EventLogger | None = None):
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)

    proc = subprocess.run([PY_BIN, pyfile, *args], cwd=str(BASE_DIR), env=env, capture_output=True, text=True)

    if evlog:
        log_event(
            evlog,
            "child_exit",
            script=str(pyfile),
            args=args,
            returncode=proc.returncode,
            stdout=(proc.stdout.strip()[:1000] if proc.stdout else ""),
            stderr=(proc.stderr.strip()[:1000] if proc.stderr else ""),
        )

    if proc.returncode != 0:
        try:
            parsed = json.loads(proc.stdout.strip() or proc.stderr.strip())
            raise RuntimeError(parsed.get("error", "command failed"))
        except Exception:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "command failed")

    try:
        return json.loads(proc.stdout.strip())
    except Exception as exc:
        raise RuntimeError(f"non-JSON child output: {exc}: {proc.stdout[:200]}")


def public_error(code: str, event_id: str, status: int):
    return jsonify({"ok": False, "error": code, "event_id": event_id}), status


def fetch_price(profile: str, symbol: str, evlog: EventLogger) -> float:
    price_script = SCRIPT_MAP[profile]["price"]
    env = SCRIPT_MAP[profile]["env"] if profile == "kraken" else {}
    result = run_script(price_script, ["--symbol", symbol], env, evlog)
    if not result.get("ok"):
        raise RuntimeError(result.get("error", "price fetch failed"))
    return float(result["price"])


def place_order(profile: str, side: str, symbol: str, qty: float, limit_px: float | None, evlog: EventLogger):
    entry = SCRIPT_MAP[profile]
    pyfile = entry["buy" if side == "buy" else "sell"]
    args = ["--symbol", symbol, "--qty", str(qty)]
    if limit_px is not None:
        args += ["--limit", str(limit_px)]
    return run_script(pyfile, args, entry["env"], evlog)


START_EVENT_ID = uuid.uuid4().hex
startup_log = make_event_logger(START_EVENT_ID)
log_event(
    startup_log,
    "startup",
    source="system",
    file=str(Path(__file__).resolve()),
    base_dir=str(BASE_DIR),
    pid=os.getpid(),
    python=PY_BIN,
    log_file=str(LOG_FILE),
    log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    default_profile=DEFAULT_BROKER_PROFILE,
    allow_live=ALLOW_LIVE,
    price_tolerance=PRICE_TOLERANCE,
    port_env=os.getenv("PORT", "8080"),
)


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "ok": True,
            "default_profile": DEFAULT_BROKER_PROFILE,
            "allow_live": ALLOW_LIVE,
            "service": "signalforge",
        }
    )


@app.route("/config", methods=["GET"])
def config():
    if not EXPOSE_CONFIG:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify(
        {
            key: {
                "paths": {name: SCRIPT_MAP[key][name] for name in ("buy", "sell", "price")},
                "allowed": sorted(SCRIPT_MAP[key]["allowed"]),
            }
            for key in SCRIPT_MAP
        }
    )


@app.route("/webhook", methods=["POST"])
def webhook():
    if not request.is_json:
        event_id = uuid.uuid4().hex
        evlog = make_event_logger(event_id)
        log_event(evlog, "rejected", reason="content_type", content_type=request.content_type)
        return public_error("invalid_content_type", event_id, 415)

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        event_id = uuid.uuid4().hex
        evlog = make_event_logger(event_id)
        log_event(evlog, "rejected", reason="invalid_json")
        return public_error("invalid_json", event_id, 400)

    event_id, source = event_identity(payload)
    evlog = make_event_logger(event_id)
    log_event(evlog, "received", source=source, payload=sanitize_payload(payload))

    try:
        profile = select_profile(payload, evlog)
    except Exception as exc:
        log_event(evlog, "error", where="select_profile", error=str(exc))
        return public_error("profile_selection_failed", event_id, 500)

    side = (payload.get("type") or "").lower()
    raw_symbol = payload.get("asset") or payload.get("symbol") or "SPY"
    symbol = norm_symbol(profile, raw_symbol)
    try:
        qty = float(payload.get("qty", 1))
    except (TypeError, ValueError):
        log_event(evlog, "rejected", reason="invalid_qty", qty=payload.get("qty"))
        return public_error("invalid_qty", event_id, 400)
    tv_price = payload.get("price")
    limit = payload.get("limit")

    if side not in ("buy", "sell"):
        log_event(evlog, "rejected", reason="invalid_side", side=side)
        return public_error("invalid_side", event_id, 400)

    if symbol not in SCRIPT_MAP[profile]["allowed"]:
        log_event(evlog, "rejected", reason="asset_not_allowed", profile=profile, symbol=symbol)
        return public_error("asset_not_allowed", event_id, 400)

    log_event(evlog, "validated", profile=profile, side=side, symbol=symbol, qty=qty, limit=limit)

    try:
        ref_price = fetch_price(profile, symbol, evlog)
        if tv_price is not None:
            try:
                parsed_tv_price = float(tv_price)
            except (TypeError, ValueError):
                log_event(evlog, "rejected", reason="invalid_price", price=tv_price)
                return public_error("invalid_price", event_id, 400)
            if abs(parsed_tv_price - ref_price) > PRICE_TOLERANCE:
                log_event(
                    evlog,
                    "price_mismatch",
                    tv=parsed_tv_price,
                    ref=ref_price,
                    tolerance=PRICE_TOLERANCE,
                    profile=profile,
                    symbol=symbol,
                )
                return (
                    jsonify(
                        {
                            "ok": False,
                            "error": "price_mismatch",
                            "tv": parsed_tv_price,
                            "ref": ref_price,
                            "tolerance": PRICE_TOLERANCE,
                            "event_id": event_id,
                        }
                    ),
                    409,
                )
        log_event(
            evlog,
            "price_checked",
            tv=(float(tv_price) if tv_price is not None else None),
            ref=ref_price,
            tolerance=PRICE_TOLERANCE,
        )
    except Exception as exc:
        log_event(evlog, "price_check_failed", profile=profile, symbol=symbol, error=str(exc))

    try:
        result = place_order(profile, side, symbol, qty, float(limit) if limit is not None else None, evlog)
        log_event(evlog, "order_result", profile=profile, side=side, symbol=symbol, result=result)
        return jsonify({"ok": True, "broker": profile, "symbol": symbol, "result": result, "event_id": event_id})
    except Exception as exc:
        log_event(evlog, "order_failed", profile=profile, side=side, symbol=symbol, error=str(exc))
        return public_error("order_failed", event_id, 500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
