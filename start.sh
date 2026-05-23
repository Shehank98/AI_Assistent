#!/usr/bin/env bash
# start.sh — Launch Jarvis (web server + optional voice loop)
# Usage:
#   ./start.sh                  — web server on :8080
#   ./start.sh --with-voice     — web server + desktop voice loop

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Load .env
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Validate
if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  echo "  ERROR: ANTHROPIC_API_KEY is not set."
  echo ""
  echo "  Create a .env file:"
  echo "    cp .env.example .env"
  echo "    # then add your key"
  echo ""
  exit 1
fi

PORT="${PORT:-8080}"

# Detect IPs
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
TAILSCALE_IP=""
if command -v tailscale &>/dev/null; then
  TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1 || true)
fi

echo ""
echo "════════════════════════════════════════════════════"
echo "  J.A.R.V.I.S  —  Starting Up"
echo "════════════════════════════════════════════════════"
echo "  Local:     http://localhost:${PORT}"
echo "  Network:   http://${LOCAL_IP}:${PORT}"
if [ -n "$TAILSCALE_IP" ]; then
  echo "  Tailscale: http://${TAILSCALE_IP}:${PORT}  ← use this on phone"
  echo ""
  echo "  Note: for voice input on Android Chrome, you need HTTPS."
  echo "  See CLAUDE.md → Remote Access for Tailscale HTTPS setup."
fi
echo "════════════════════════════════════════════════════"
echo ""

# Optional desktop voice loop
if [[ "$*" == *"--with-voice"* ]]; then
  echo "[Jarvis] Starting desktop voice loop..."
  python3 jarvis.py --voice &
  VOICE_PID=$!
  trap "kill $VOICE_PID 2>/dev/null; echo 'Voice loop stopped.'" EXIT
fi

exec python3 -m uvicorn server:app --host 0.0.0.0 --port "$PORT" --workers 1
