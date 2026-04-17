#!/usr/bin/env python3
# main.py — unified broker router for TradingView webhooks
import os, sys, json, subprocess, logging
from pathlib import Path
from flask import Flask, request, jsonify

# ---------- bootstrap ----------
app = Flask(__name__)
log = logging.getLogger("broker")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                    format="%(asctime)s %(levelname)s %(message)s")

BASE_DIR = Path(__file__).resolve().parent
PY_BIN   = sys.executable

# Defaults & safety
DEFAULT_BROKER_PROFILE = os.getenv("BROKER_PROFILE", "alpaca_paper").lower()    # kraken | alpaca_paper | alpaca_live
ALLOW_LIVE             = os.getenv("ALLOW_LIVE", "false").lower() == "true"
PRICE_TOLERANCE        = float(os.getenv("PRICE_TOLERANCE", "0.50"))            # USD threshold to reject mismatches

# ---------- script registry ----------
# All paths are anchored to BASE_DIR. Child scripts must accept:
#   --symbol <sym> [--qty <n>] [--limit <px>]
SCRIPT_MAP = {
    "kraken": {
        "buy":   str(BASE_DIR / "kraken" / "buy.py"),
        "sell":  str(BASE_DIR / "kraken" / "sell.py"),
        "price": str(BASE_DIR / "kraken" / "getPrice.py"),
        "allowed": {"BTC/USD", "ETH/USD"},
        "env": {}
    },
    # Alpaca paper/live both use the same buy/sell scripts; mode is injected via env.
    "alpaca_paper": {
        "buy":   str(BASE_DIR / "alpaca" / "alpacaBuy.py"),
        "sell":  str(BASE_DIR / "alpaca" / "alpacaSell.py"),
        # NOTE: price script for Alpaca is ALWAYS the live data script
        "price": str(BASE_DIR / "alpaca" / "alpacaGetPrice.py"),
        "allowed": {"SPY", "AAPL"},
        "env": {"ALPACA_MODE": "paper"}
    },
    "alpaca_live": {
        "buy":   str(BASE_DIR / "alpaca" / "alpacaBuy.py"),
        "sell":  str(BASE_DIR / "alpaca" / "alpacaSell.py"),
        "price": str(BASE_DIR / "alpaca" / "alpacaGetPrice.py"),  # same live data script
        "allowed": {"SPY", "AAPL"},
        "env": {"ALPACA_MODE": "live"}  # honored only if ALLOW_LIVE=true
    },
}

# Optional symbol normalization per profile (tweak as needed)
ASSET_MAP = {
    "kraken":       {"BTCUSD": "BTC/USD", "ETHUSD": "ETH/USD"},
    "alpaca_paper": {"SPY": "SPY", "AAPL": "AAPL"},
    "alpaca_live":  {"SPY": "SPY", "AAPL": "AAPL"},
}

# ---------- helpers ----------
def _ensure_files(profile: str):
    entry = SCRIPT_MAP[profile]
    for key in ("buy", "sell", "price"):
        p = Path(entry[key])
        if not p.is_file():
            raise FileNotFoundError(f"Missing script for {profile}:{key} → {p}")

def select_profile(payload: dict) -> str:
    requested = (payload.get("broker_profile") or DEFAULT_BROKER_PROFILE).lower()
    if requested not in SCRIPT_MAP:
        log.warning("unknown broker_profile=%s; fallback=%s", requested, DEFAULT_BROKER_PROFILE)
        requested = DEFAULT_BROKER_PROFILE
    if requested == "alpaca_live" and not ALLOW_LIVE:
        log.warning("alpaca_live requested but ALLOW_LIVE=false; fallback=%s", DEFAULT_BROKER_PROFILE)
        requested = DEFAULT_BROKER_PROFILE
    _ensure_files(requested)
    return requested

def norm_symbol(profile: str, sym: str) -> str:
    return ASSET_MAP.get(profile, {}).get(sym, sym)

def run_script(pyfile: str, args: list[str], extra_env: dict | None):
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    # Keep all child scripts running with BASE_DIR as cwd to simplify opens/imports
    cmd = [PY_BIN, pyfile, *args]
    proc = subprocess.run(cmd, cwd=str(BASE_DIR), env=env,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        # Try to pass through JSON error if present
        try:
            j = json.loads(proc.stdout.strip() or proc.stderr.strip())
            raise RuntimeError(j.get("error", "command failed"))
        except Exception:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "command failed")
    # Must be one clean JSON line
    try:
        return json.loads(proc.stdout.strip())
    except Exception as e:
        raise RuntimeError(f"non-JSON child output: {e}: {proc.stdout[:200]}")

def fetch_price(profile: str, symbol: str) -> float:
    """
    For Alpaca: ALWAYS uses the live data script (SCRIPT_MAP[profile]['price'] points to live-only client).
    For Kraken: uses Kraken's price script.
    """
    price_script = SCRIPT_MAP[profile]["price"]
    # For alpaca_paper/alpaca_live, the price script reads LIVE keys only; no env injection required.
    env = SCRIPT_MAP[profile]["env"] if profile == "kraken" else {}
    out = run_script(price_script, ["--symbol", symbol], env)
    if not out.get("ok"):
        raise RuntimeError(out.get("error", "price fetch failed"))
    return float(out["price"])

def place_order(profile: str, side: str, symbol: str, qty: float, limit_px: float | None):
    entry = SCRIPT_MAP[profile]
    pyfile = entry["buy" if side == "buy" else "sell"]
    args = ["--symbol", symbol, "--qty", str(qty)]
    if limit_px is not None:
        args += ["--limit", str(limit_px)]
    # Inject ALPACA_MODE for alpaca_* profiles; Kraken needs nothing extra
    env = entry["env"]
    out = run_script(pyfile, args, env)
    return out

# ---------- routes ----------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "default_profile": DEFAULT_BROKER_PROFILE,
        "allow_live": ALLOW_LIVE,
        "base_dir": str(BASE_DIR),
        "python": PY_BIN
    })

@app.route("/config", methods=["GET"])
def config():
    return jsonify({
        k: {"paths": {x: SCRIPT_MAP[k][x] for x in ("buy","sell","price")},
            "allowed": sorted(list(SCRIPT_MAP[k]["allowed"]))}
        for k in SCRIPT_MAP
    })

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.get_json(force=True)
    profile = select_profile(payload)

    # Extract + normalize core fields
    side   = (payload.get("type") or "").lower()   # "buy" | "sell"
    rawsym = payload.get("asset") or payload.get("symbol") or "SPY"
    sym    = norm_symbol(profile, rawsym)
    qty    = float(payload.get("qty", 1))
    tv_px  = payload.get("price")
    limit_ = payload.get("limit")

    if side not in ("buy", "sell"):
        return jsonify({"ok": False, "error": "invalid side"}), 400
    if sym not in SCRIPT_MAP[profile]["allowed"]:
        return jsonify({"ok": False, "error": f"asset {sym} not allowed for {profile}"}), 400

    # Real-time parity check (skip if TV price missing)
    try:
        ref = fetch_price(profile, sym)
        if tv_px is not None and abs(float(tv_px) - ref) > PRICE_TOLERANCE:
            log.warning("[%s] price mismatch TV=%.4f REF=%.4f tol=%.2f sym=%s",
                        profile.upper(), float(tv_px), ref, PRICE_TOLERANCE, sym)
            return jsonify({"ok": False, "error": "price_mismatch",
                            "tv": float(tv_px), "ref": ref, "tolerance": PRICE_TOLERANCE}), 409
    except Exception as e:
        log.warning("[%s] ref price fetch failed for %s: %s (continuing)",
                    profile.upper(), sym, e)

    # Place order
    try:
        result = place_order(profile, side, sym, qty, float(limit_) if limit_ is not None else None)
        log.info("[%s] %s %s qty=%s limit=%s -> %s", profile.upper(), side, sym, qty, limit_, result.get("status"))
        return jsonify({"ok": True, "broker": profile, "symbol": sym, "result": result})
    except Exception as e:
        log.exception("[%s] order failed for %s %s", profile.upper(), side, sym)
        return jsonify({"ok": False, "error": str(e)}), 500

# ---------- entry ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
