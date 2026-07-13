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

echo "[setup] locate a WORKING chromium (verify --version; broken snap stubs are rejected)"
CHROME=""
_ok(){ [ -x "$1" ] && "$1" --version >/dev/null 2>&1; }   # a real chromium answers --version; the /usr/bin snap stub errors
# 1) Playwright-bundled chromium — pre-installed in the Claude Code sandbox (most reliable here)
for c in /opt/pw-browsers/chromium*/chrome-linux/chrome "$HOME"/.cache/ms-playwright/chromium*/chrome-linux/chrome; do
  if _ok "$c"; then CHROME="$c"; break; fi
done
# 2) system chromium/chrome on PATH — but VERIFY it runs (skips the broken /usr/bin/chromium-browser snap stub)
if [ -z "$CHROME" ]; then
  for c in chromium chromium-browser google-chrome google-chrome-stable; do
    p="$(command -v "$c" 2>/dev/null)"; if [ -n "$p" ] && _ok "$p"; then CHROME="$p"; break; fi
  done
fi
# 3) install: apt (if root/sudo), then Playwright's chromium (no sudo). Re-verify after each.
if [ -z "$CHROME" ]; then
  (apt-get update -y && apt-get install -y chromium fontconfig) >/dev/null 2>&1 \
    || (sudo apt-get update -y && sudo apt-get install -y chromium fontconfig) >/dev/null 2>&1 || true
  for c in chromium chromium-browser google-chrome google-chrome-stable; do
    p="$(command -v "$c" 2>/dev/null)"; if [ -n "$p" ] && _ok "$p"; then CHROME="$p"; break; fi
  done
fi
if [ -z "$CHROME" ]; then
  pip install -q playwright >/dev/null 2>&1 && python -m playwright install chromium >/dev/null 2>&1
  for c in "$HOME"/.cache/ms-playwright/chromium*/chrome-linux/chrome /opt/pw-browsers/chromium*/chrome-linux/chrome; do
    if _ok "$c"; then CHROME="$c"; break; fi
  done
fi

if [ -n "$CHROME" ]; then
  echo "CHROME_BIN=$CHROME"
else
  echo "CHROME_BIN="  # renderers will report failure; the routine must flag this loudly
  echo "[setup] WARNING: could not find or install chromium" 1>&2
fi
