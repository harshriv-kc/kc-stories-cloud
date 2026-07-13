#!/usr/bin/env bash
# One-time-per-run environment setup for the KC Stories cloud routine (Linux).
# Installs: Python deps, a headless Chromium, and the bundled Nirmala UI font so the
# renderers produce cards/badges pixel-identical to the local Windows setup.
# Safe to re-run. Prints CHROME_BIN=<path> at the end — export it before running the renderers.
set -u

echo "[setup] python deps"
pip install -q pillow requests >/dev/null 2>&1 || pip3 install -q pillow requests >/dev/null 2>&1 || true

echo "[setup] install bundled Nirmala UI font"
mkdir -p "$HOME/.fonts"
cp -f fonts/Nirmala.ttc "$HOME/.fonts/" 2>/dev/null || true
fc-cache -f "$HOME/.fonts" >/dev/null 2>&1 || fc-cache -f >/dev/null 2>&1 || true

echo "[setup] locate/install chromium"
CHROME=""
for c in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$c" >/dev/null 2>&1; then CHROME="$(command -v "$c")"; break; fi
done
if [ -z "$CHROME" ]; then
  # try apt (root or sudo); many sandboxes are root
  (apt-get update -y && apt-get install -y chromium fontconfig) >/dev/null 2>&1 \
    || (sudo apt-get update -y && sudo apt-get install -y chromium fontconfig) >/dev/null 2>&1 || true
  for c in chromium chromium-browser google-chrome google-chrome-stable; do
    if command -v "$c" >/dev/null 2>&1; then CHROME="$(command -v "$c")"; break; fi
  done
fi
if [ -z "$CHROME" ]; then
  # last resort: Playwright's bundled chromium (no apt/sudo needed)
  pip install -q playwright >/dev/null 2>&1 && python -m playwright install chromium >/dev/null 2>&1
  CHROME="$(python - <<'PY'
import glob, os
hits = sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium*/chrome-linux/chrome")))
print(hits[-1] if hits else "")
PY
)"
fi

if [ -n "$CHROME" ]; then
  echo "CHROME_BIN=$CHROME"
else
  echo "CHROME_BIN="  # renderers will report failure; the routine must flag this loudly
  echo "[setup] WARNING: could not find or install chromium" 1>&2
fi
