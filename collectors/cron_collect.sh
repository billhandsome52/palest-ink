#!/bin/bash
# Palest Ink - Cron Collection Entry Point
# Runs all collectors in sequence: browsers first, then content, then others

PALEST_INK_DIR="$HOME/.palest-ink"
BIN_DIR="$PALEST_INK_DIR/bin"
LOCKFILE="$PALEST_INK_DIR/tmp/collect.lock"

# Prevent concurrent runs
if [ -f "$LOCKFILE" ]; then
    LOCK_PID=$(cat "$LOCKFILE" 2>/dev/null)
    if kill -0 "$LOCK_PID" 2>/dev/null; then
        echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Collection already running (PID $LOCK_PID), skipping."
        exit 0
    fi
    # Stale lock, remove it
    rm -f "$LOCKFILE"
fi

echo $$ > "$LOCKFILE"
trap "rm -f '$LOCKFILE'" EXIT

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting collection..."

# Phase 0: App focus (fastest, highest priority)
timeout 5 python3 "$BIN_DIR/collect_app.py" 2>&1 || true

# Phase 1: Browser history (creates web_visit records with content_pending=true)
python3 "$BIN_DIR/collect_chrome.py" 2>&1 || true
python3 "$BIN_DIR/collect_safari.py" 2>&1 || true

# Phase 2: Content fetching (fills in content_summary for pending URLs)
python3 "$BIN_DIR/collect_content.py" 2>&1 || true

# Phase 3: Other collectors
python3 "$BIN_DIR/collect_shell.py" 2>&1 || true
python3 "$BIN_DIR/collect_vscode.py" 2>&1 || true
python3 "$BIN_DIR/collect_git.py" 2>&1 || true

# Phase 4: Filesystem events (find can be slow, run last)
timeout 15 python3 "$BIN_DIR/collect_fsevent.py" 2>&1 || true

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Collection complete."
