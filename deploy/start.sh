#!/bin/sh
set -eu

BASE_DIR="${BASE_DIR:-/root/projects/codex/alpaca-bot/development/tradingBot/app}"
VENV_DIR="${VENV_DIR:-/root/projects/test/bot/venv}"
RUNTIME_DIR="${RUNTIME_DIR:-/root/projects/codex/runtime}"
TUNNEL_NAME="${TUNNEL_NAME:-dispatcher}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
WORKERS="${WORKERS:-2}"
TIMEOUT="${TIMEOUT:-60}"

mkdir -p "$RUNTIME_DIR"

if [ -f "$RUNTIME_DIR/cloudflared.pid" ] && kill -0 "$(cat "$RUNTIME_DIR/cloudflared.pid")" 2>/dev/null; then
  echo "cloudflared already running: $(cat "$RUNTIME_DIR/cloudflared.pid")"
else
  rm -f "$RUNTIME_DIR/cloudflared.pid"
  nohup cloudflared tunnel run "$TUNNEL_NAME" >"$RUNTIME_DIR/cloudflared.log" 2>&1 &
  echo $! >"$RUNTIME_DIR/cloudflared.pid"
  echo "started cloudflared: $(cat "$RUNTIME_DIR/cloudflared.pid")"
fi

if [ -f "$RUNTIME_DIR/alpaca-gunicorn.pid" ] && kill -0 "$(cat "$RUNTIME_DIR/alpaca-gunicorn.pid")" 2>/dev/null; then
  echo "gunicorn already running: $(cat "$RUNTIME_DIR/alpaca-gunicorn.pid")"
else
  rm -f "$RUNTIME_DIR/alpaca-gunicorn.pid"
  cd "$BASE_DIR"
  . "$VENV_DIR/bin/activate"
  nohup gunicorn --bind "$HOST:$PORT" --workers "$WORKERS" --timeout "$TIMEOUT" main:app >"$RUNTIME_DIR/alpaca-gunicorn.log" 2>&1 &
  echo $! >"$RUNTIME_DIR/alpaca-gunicorn.pid"
  echo "started gunicorn: $(cat "$RUNTIME_DIR/alpaca-gunicorn.pid")"
fi

echo "---"
echo "cloudflared log:"
tail -n 10 "$RUNTIME_DIR/cloudflared.log" 2>/dev/null || true
echo "---"
echo "gunicorn log:"
tail -n 20 "$RUNTIME_DIR/alpaca-gunicorn.log" 2>/dev/null || true
