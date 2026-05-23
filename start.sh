#!/usr/bin/env bash
# start.sh — Launch Jarvis web server (+ optional desktop voice loop)
# Usage:
#   ./start.sh                  — web server only (access from phone/browser)
#   ./start.sh --with-voice     — web server + desktop voice loop

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Load .env if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Validate required env var
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  echo "  ERROR: ANTHROPIC_API_KEY is not set."
  echo ""
  echo "  Option 1 — create a .env file:"
  echo "    echo 'ANTHROPIC_API_KEY=sk-ant-...' > .env"
  echo ""
  echo "  Option 2 — export in your shell:"
  echo "    export ANTHROPIC_API_KEY=sk-ant-..."
  echo ""
  exit 1
fi

PORT="${PORT:-8080}"

# Detect local IP
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

# Detect Tailscale IP (if installed)
TAILSCALE_IP=""
if command -v tailscale &>/dev/null; then
  TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1 || true)
fi

echo ""
echo "════════════════════════════════════════════════"
echo "  J.A.R.V.I.S  —  Starting"
echo "════════════════════════════════════════════════"
echo "  Local:     http://localhost:${PORT}"
echo "  Network:   http://${LOCAL_IP}:${PORT}"
if [ -n "$TAILSCALE_IP" ]; then
  echo "  Tailscale: http://${TAILSCALE_IP}:${PORT}  ← use this on phone"
fi
echo ""
echo "  Open the URL above in Chrome on your phone."
echo "  For HTTPS (needed for voice on Android):"
echo "  See CLAUDE.md → Remote Access section."
echo "════════════════════════════════════════════════"
echo ""

# Optional: start desktop voice loop in background
if [[ "$*" == *"--with-voice"* ]]; then
  echo "[Jarvis] Starting desktop voice loop in background..."
  python3 jarvis.py --voice &
  VOICE_PID=$!
  trap "echo 'Stopping voice loop...'; kill $VOICE_PID 2>/dev/null" EXIT
fi

# Start web server (foreground — Ctrl+C stops everything)
exec python3 -m uvicorn server:app --host 0.0.0.0 --port "$PORT" --workers 1
