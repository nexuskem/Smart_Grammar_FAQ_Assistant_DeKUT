#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# setup_ngrok.sh  —  Install ngrok binary + pyngrok for the DeKUT FAQ Bot
# ──────────────────────────────────────────────────────────────────────────────
# Run once:   bash setup_ngrok.sh
# Then:       ngrok authtoken <YOUR_TOKEN>
#             python3 start_whatsapp_bot.py
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

info()  { echo -e "${GREEN}→${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
error() { echo -e "${RED}✗${NC} $*"; exit 1; }

INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$INSTALL_DIR"

# ── 1. Install ngrok binary ────────────────────────────────────────────────────
info "Downloading ngrok binary …"

ARCH=$(uname -m)
case "$ARCH" in
  x86_64)  NGROK_ZIP="ngrok-v3-stable-linux-amd64.tgz" ;;
  aarch64) NGROK_ZIP="ngrok-v3-stable-linux-arm64.tgz" ;;
  armv7l)  NGROK_ZIP="ngrok-v3-stable-linux-arm.tgz"   ;;
  *)        error "Unsupported architecture: $ARCH" ;;
esac

NGROK_URL="https://bin.equinox.io/c/bNyj1mQVY4c/$NGROK_ZIP"
TMP_DIR=$(mktemp -d)

curl -fsSL "$NGROK_URL" -o "$TMP_DIR/$NGROK_ZIP"
tar -xzf "$TMP_DIR/$NGROK_ZIP" -C "$TMP_DIR"
install -m 755 "$TMP_DIR/ngrok" "$INSTALL_DIR/ngrok"
rm -rf "$TMP_DIR"

info "ngrok installed → $INSTALL_DIR/ngrok"

# ── 2. Add to PATH if needed ──────────────────────────────────────────────────
if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
  warn "$INSTALL_DIR is not in your PATH."
  echo "  Add this line to ~/.bashrc or ~/.zshrc:"
  echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
  echo "  Then run:  source ~/.bashrc"
fi

# ── 3. Install pyngrok into .venv ─────────────────────────────────────────────
VENV_PIP="$(dirname "$(realpath "$0")")/.venv/bin/pip"

if [ -f "$VENV_PIP" ]; then
  info "Installing pyngrok into .venv …"
  "$VENV_PIP" install pyngrok --quiet
  info "pyngrok installed."
else
  warn ".venv not found. Installing pyngrok system-wide (user install) …"
  pip install pyngrok --user --quiet 2>/dev/null || \
    pip install pyngrok --break-system-packages --quiet || \
    warn "Could not install pyngrok automatically. Run: pip install pyngrok"
fi

# ── 4. Done ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}✓ ngrok setup complete!${NC}"
echo ""
echo "  NEXT STEPS:"
echo "  ───────────"
echo "  1. Get a free ngrok authtoken at  https://ngrok.com/signup"
echo "  2. Run:  ngrok authtoken <YOUR_TOKEN>"
echo "  3. Run:  python3 start_whatsapp_bot.py"
echo ""
