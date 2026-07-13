# kc-stories-cloud

Daily **KC Stories** pipeline — generates + publishes the 3 story tags (mandi_bhav, fmcg,
trending_news = 3 commodity + 3 FMCG + 1 news), their card slides + entry badges, and the
WebEngage push JSON. Runs as a scheduled **Claude Code cloud routine** (~12:04 PM IST) — no laptop.

## Layout
```
kc-card-render.py     deterministic 1080x1920 story-card compositor (headless Chromium + Nirmala UI)
kc-badge-banner.py    circular entry-badge / PN compositor (headless Chromium + Nirmala UI + PIL ring)
fonts/Nirmala.ttc     ⭐ bundled Nirmala UI font (installed at setup so Hindi renders identically to local)
setup.sh              installs chromium + the font + pillow/requests; prints CHROME_BIN=<path>
used-picks-log.json   ⭐ THE LEDGER — 12-day news_id dedup (source of truth)
specs/                the authoritative pipeline + templates
  kc-stories-workflow.md          end-to-end pipeline + mandatory QC (slide layout-lock, badge ring-normalize)
  kc-image-prompt-template.md     slide photo prompt scaffold
  kc-badge-template.md            badge prompt + flat-ring normalize
  webengage-stories-automation.md WebEngage multi_icon push JSON spec
```
Runtime artifacts (photo_*, card_*, badge_*, v*_*, runs/, browser profiles) are git-ignored.

## Renderers — the Windows→Linux port
The cards/badges are composited from locked HTML/CSS via **headless Chromium** using **`'Nirmala UI'`**
(the only Windows dependency). In the cloud we bundle `fonts/Nirmala.ttc` and install it at setup, so
`font-family:'Nirmala UI'` resolves and output is **pixel-identical** to the local Windows renders.
Both scripts auto-detect the Chromium binary (env `CHROME_BIN`, then `chromium`/`google-chrome` on PATH,
then standard Linux paths, then Windows). Run `bash setup.sh`, `export CHROME_BIN=<printed path>`, then run them.

## The ledger is the whole point
`used-picks-log.json` is mutable state: before selection the routine unions every `news_id` in the last
`dedup_window_days` (12) and HARD-EXCLUDES repeats; after publish it appends today's run. **The routine must
commit the updated ledger back to `main` at the end of every run**, or the next day repeats news.

## Nightly flow (the routine)
1. `git pull origin main` (latest ledger) → `bash setup.sh` → `export CHROME_BIN=...`
2. Read `specs/` (workflow is authoritative). Pull today's pools via jack + Birbal + Mixpanel.
3. Dedup vs the ledger → pick 3 commodity + 3 FMCG + 1 news.
4. Gemini photo per card → `kc-card-render.py` → upload each card via jack. Badges via `kc-badge-banner.py`.
5. Publish via jack (update_story + update_story_entry_badges). Emit the WebEngage push JSON.
6. Append the ledger → `git add used-picks-log.json && git commit && git push origin HEAD:main`.

## Connectors / deps
jack (B2B) · Birbal · Mixpanel · Slack (auto-attached). Python 3 + pillow + requests + a headless Chromium.
