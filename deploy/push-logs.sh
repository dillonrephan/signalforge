#!/bin/sh
set -eu

APP_LOG_DIR="${APP_LOG_DIR:-/root/projects/codex/alpaca-bot/development/tradingBot/app/logs}"
RUNTIME_DIR="${RUNTIME_DIR:-/root/projects/codex/runtime}"
STAGING_DIR="${STAGING_DIR:-/tmp/signalforge-logpush}"
REMOTE_HOST="${REMOTE_HOST:-leviathan}"
REMOTE_USER="${REMOTE_USER:-logdrop}"
REMOTE_BASE_DIR="${REMOTE_BASE_DIR:-/srv/marketdrop/incoming/dispatcher}"
SSH_KEY="${SSH_KEY:-}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
PACKAGE_DIR="$STAGING_DIR/$STAMP"
ARCHIVE_BASENAME="dispatcher-logs-$STAMP.tgz"
ARCHIVE_PATH="$STAGING_DIR/$ARCHIVE_BASENAME"

mkdir -p "$PACKAGE_DIR/app" "$PACKAGE_DIR/runtime"
rm -f "$ARCHIVE_PATH"

copy_if_exists() {
  src="$1"
  dest_dir="$2"
  if [ -f "$src" ]; then
    cp "$src" "$dest_dir/"
  fi
}

copy_matches() {
  pattern="$1"
  dest_dir="$2"
  found=0
  for src in $pattern; do
    if [ -f "$src" ]; then
      cp "$src" "$dest_dir/"
      found=1
    fi
  done
  return "$found"
}

copy_matches "$APP_LOG_DIR"/broker.log* "$PACKAGE_DIR/app" || true
copy_matches "$RUNTIME_DIR"/alpaca-gunicorn.log* "$PACKAGE_DIR/runtime" || true
copy_matches "$RUNTIME_DIR"/cloudflared.log* "$PACKAGE_DIR/runtime" || true

cat >"$PACKAGE_DIR/manifest.txt" <<EOF
timestamp_utc=$STAMP
source_host=$(hostname)
app_log_dir=$APP_LOG_DIR
runtime_dir=$RUNTIME_DIR
EOF

tar -C "$STAGING_DIR" -czf "$ARCHIVE_PATH" "$STAMP"

SSH_OPTS=""
if [ -n "$SSH_KEY" ]; then
  SSH_OPTS="-i $SSH_KEY"
fi

ssh $SSH_OPTS "$REMOTE_USER@$REMOTE_HOST" "mkdir -p '$REMOTE_BASE_DIR'"
scp $SSH_OPTS "$ARCHIVE_PATH" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_BASE_DIR/$ARCHIVE_BASENAME"

rm -rf "$PACKAGE_DIR" "$ARCHIVE_PATH"
echo "shipped $ARCHIVE_BASENAME to $REMOTE_USER@$REMOTE_HOST:$REMOTE_BASE_DIR"
