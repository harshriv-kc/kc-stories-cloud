# KC STORIES — DAILY GENERATOR (END-TO-END, AUTOPILOT)

Fully automated daily refresh of the 3 live KC Stories tags + their entry badges + the WebEngage push (created and **scheduled automatically for 16:30 IST**, Step 12b). Runs on one trigger, publishes on its own.

## TRIGGERS
"today's KC stories", "daily prompts", "make stories", "kc stories", "todays", or any equivalent → run the whole pipeline below end-to-end and **publish without asking**.

## ⚑ AUTOPILOT RULES
- **No clarifying questions. No pick-confirmation gate. No "publish?" gate.** Run start → live in one go.
- The only human action is the **one-time client "Allow always"** for jack write tools (`update_story`, `update_story_entry_badges`) — that is a Claude-client permission the operator sets once; it is not a question to ask.
- **Auto-swap, don't halt:** if a pick fails the self-check (below), silently swap to the next pool candidate and note it in the final summary. Never stop the run for a swap.
- **Offer swaps inline in the final summary**, not upfront.
- **Hard stop only** on a genuine tool failure/inaccessibility (per operator standing rule): say which tool failed and ask how to proceed. A documented precondition (e.g. Birbal "codebase context required") is NOT a failure — satisfy it and continue.

## THE 3 FIXED TARGETS (never change)
| Tag | story_id (permanent) | Slides | Badge label |
|---|---|---|---|
| `mandi_bhav` | `51f7efb8-8d3f-4e21-a63b-56151306478c` | 3 (commodity) | Mandi Bhav |
| `fmcg` | `a93e34ab-3a8c-4cbe-b7de-642e4b50e4b2` | 3 (FMCG) | FMCG Scheme |
| `trending_news` | `16c9eaae-3c3e-47ff-9030-4b4362499045` | 1 (news) | Trending News |

Default daily fill = **3 commodity + 3 FMCG + 1 news** (matches the live slide counts). Confirm counts each run via `jack:kc_stories_overview`.

---

## PIPELINE

### 1. Context
- `jack:kc_stories_overview` → confirm the 3 tags, story_ids, slide counts, badges.
- `Birbal:get_repo_context(repo="Kirana-Club")`. **Birbal context expires between queries** — re-run `get_repo_context` or a quick `search_code(...)` before EVERY `query_db` call, or it errors "codebase context required". This is normal, not a failure.

### 2. Today's in-house posts (`database="main"`)
```sql
SELECT id, JSON_UNQUOTE(JSON_EXTRACT(request_data,'$.post_name')) post_name,
       JSON_UNQUOTE(JSON_EXTRACT(request_data,'$.post_title')) post_title,
       LEFT(JSON_UNQUOTE(JSON_EXTRACT(news_api_request,'$.data.content')),1500) content
FROM news_generation_logs
WHERE DATE(FROM_UNIXTIME(JSON_UNQUOTE(JSON_EXTRACT(news_api_request,'$.data.visible_from'))/1000)) = CURDATE()
ORDER BY id ASC
```
(Trust `visible_from`; no title-prefix date filter.) Expected: ~3 commodity (soya tel / दाल-शक्कर / Other commodity) + news/scheme + digests.

### 3. Dedup (LEDGER is PRIMARY — `used-picks-log.json`)
**The authoritative dedup is the local ledger `KC Stories/used-picks-log.json`, NOT Mixpanel/chat-history.** Mixpanel `itemID` dedup is broken (itemID = slide UUID, not news_id) and chat-history is unreliable — both caused event-level news repeats (e.g. USHA/Hajmola repeating). The ledger fixes this deterministically by logging the actual published `ref_id` (news_id) each day.
- **Read it now:** load the file, take every run whose `date` is within `dedup_window_days` (default 12) of today, and union all `picks[].news_id` **and** `also_shown[].news_id` → that set is `recently_used_news_ids`.
- **Hard exclude:** any candidate — in-house **or** MP, commodity/FMCG/news — whose `news_id` is in `recently_used_news_ids` is disqualified. Auto-swap to the next pool candidate (never publish a repeat; note the swap in the summary). This applies to the persistent high-LR FMCG UGC posts that otherwise recur day after day.
- **⚑ BRAND-LEVEL DEDUP (mandatory — news_id dedup does NOT catch a brand re-posted under a NEW news_id).** The same FMCG scheme recurs day-to-day because different retailers post it and each copy gets a fresh `news_id` — so `news_id` dedup alone lets e.g. **Oral-B / Colgate / Close Up** reappear every 2–3 days (each a distinct UUID). To stop this deterministically, the ledger stores a normalized **`brand`** token per pick (Step 13). Build `recently_used_brands` = the union of every `picks[].brand` (and `also_shown[].brand`) over **`brand_dedup_window_days` = 7** of today, and **HARD-EXCLUDE any FMCG candidate whose brand is in that set** (auto-swap to the next pool candidate; note it in the summary). Normalize brand to a lowercase product-line token — `oral-b`, `close-up`, `colgate`, `navratna`, `ghadi`, `ujala`, `dabur-hajmola`, `patanjali-dant-kanti`, `lux`, `vim`, `eno`, `vicks`, `parle`, `cadbury`, `pulse`, `alpenliebe`, `himalaya`, `medimix`, `lifebuoy`, … — and match on that token, NOT the full label. If an older run lacks a `brand` field, derive it from its label text as a fallback. (Commodity/news are day-fresh in-house posts, so brand-dedup is FMCG-only; for commodity just avoid the same commodity+direction within 3 days — soft.)
- Soft secondary signals (do NOT replace the ledger): `conversation_search` / `search_session_transcripts` for recent headlines; and `database="community"` `SELECT news_id, LEFT(title,120) title FROM nc_published_posts WHERE created_at >= UNIX_TIMESTAMP(NOW() - INTERVAL 7 DAY)*1000 ORDER BY created_at DESC LIMIT 200`.
- The ledger is **written after publish** — see Step 13. If the file is missing, create it from the template in Step 13 and proceed (first run has nothing to exclude).

### 4. Mixpanel LR pools — `Get-Report(bookmark_id=90465031, project_id=2551336, skip_results=False)`
Result is too large for context → it lands in a local tool-results file (path is in the error envelope; on Windows e.g. `C:\Users\...\tool-results\...Get-Report-*.txt`). **Delegate parsing to a subagent** (keeps the 200k JSON out of main context). Parsing recipe:
- The file may already be the parsed report object (then rows are at `data['results']['Like Rate']['rows']`), or wrapped as `outer[0]['text']` → `json.loads()`. Probe with python first.
- Each row: `row[0]` = `"uuid, level4"`; for `"uuid, $overall"` rows `row[1]` = LR float; for `"uuid, level4"` rows `row[1]` = nested dict (walk first non-`$overall` key for tag, then for headline).
- Pools: commodity = `teji_mandi`; news = `news`. **FMCG = 4 segments** (the `rate_and_margin` bucket was removed 2026-06-25): level4 `fmcg_product_change`, level4 `new_product_launch`, and level4 **`scheme`** which is split by its **level5 sub-label** into `Retailer Scheme` and `Consumer Scheme` (read LR at `val['<sublabel>']['$overall']['all']` for scheme rows; `val['$overall']['all']` for the standalone level4 segments). Sort by LR desc. (`new_product_launch` / `fmcg_product_change` pools are often tiny — that's fine.) Record each chosen post's segment — it drives the card heading/colour/representation (Step 8b).

### 5. Selection
- **Commodity (3):** today's in-house first (jeera/dal/shakkar/other — SKIP सोना-चांदी, SKIP रुझान digests, SKIP same commodity+direction as a recent day, flag over-covered like सोया तेल). Top up from MP `teji_mandi` by LR. Must have a concrete ₹ figure.
- **FMCG (3):** **pick the top 3 across ALL 4 segments purely by Like Rate desc** (no per-segment quota — a day can be 3 schemes, or 1 of each, whatever LR says), after dedup + body-verify. Drop only genuinely hyper-local (single city/distributor) or vague no-number posts. Tier 2/3 regional brands are valid — brand whitelist is a soft signal only.
  - **The chosen post's segment sets the card heading + accent + representation** (built in Step 8b, CSS in `kc-card-render.py`):
    | Segment (report) | Masthead | Stripe/accent | Representation (price line) | Grid labels |
    |---|---|---|---|---|
    | `scheme`→Retailer Scheme | **FMCG व्यापारी स्कीम** | green `#1E7A3C` | green **offer pill** — free-goods, e.g. "1 पैकेट पर 5 नग फ्री" (+ ₹ margin in sub if given) | स्कीम / फायदा |
    | `scheme`→Consumer Scheme | **FMCG ग्राहक ऑफर** | blue `#1F5AA6` | blue **offer pill** — combo ratio, e.g. "4 + 1 फ्री" (+ MRP if given) | ऑफर / ग्राहक को |
    | `new_product_launch` | **FMCG नया प्रोडक्ट लॉन्च** | amber `#C8772A` | **`नया` pill + MRP ₹X** | नया क्या / फायदा |
    | `fmcg_product_change` | **FMCG प्रोडक्ट बदलाव** | black `#1A1A1A` | **ARROW (this segment only)** — ₹X→₹Y (price) or 110g→100g (weight) | बदलाव / फायदा |
  - ⚠ The ▲▼/→ arrow is for `fmcg_product_change` ONLY. Schemes use the offer pill; launch uses the नया pill. Never force a scheme/launch post into a ₹X→₹Y shape.
  - **Masthead = a small gold "FMCG" eyebrow over the segment name** (compositor: FMCG cards set `eyebrow="FMCG"` + `label="<segment name>"`, e.g. व्यापारी स्कीम / ग्राहक ऑफर / नया प्रोडक्ट लॉन्च / प्रोडक्ट बदलाव). Commodity/news omit the eyebrow (single large heading). Keeps the long segment names from spanning the whole masthead.
- **News (1):** today's in-house first. SKIP scam/fraud/arrest bait (नकली, फर्जी, ठगी, QR scam). Prefer monsoon / crop / policy / scheme / market-impact. Else top-LR MP news (skip bait).
- **Direction balance:** aim for a mix; never all-RED or all-GREEN (soft). The single मंदी/GREEN commodity is worth keeping for balance even if its commodity is over-covered.

### 6. ⚑ BODY VERIFY (mandatory — catches the LR-headline ≠ real-content trap)
For every UGC/MP pick, pull the actual body before generating (`database="community"`):
```sql
SELECT s.published_id, LEFT(p.post_description,700) body
FROM ugc_posts_stats s JOIN ugc_posts p ON p.post_id = s.post_id
WHERE s.published_id IN ('<uuid>', ...)
```
- `published_id` = the `news_id` redirect target.
- **Reject + auto-swap** any pick whose body has no concrete ₹ figure, or whose body doesn't match its LR-report headline. Note the mismatch in the summary for eng.
- Lock exact figures (price, MRP, margin, weight) from the body — these go on the card.

### 7. Resolve in-house news_ids (`database="community"`)
```sql
SELECT news_id, LEFT(title,140) title FROM nc_published_posts
WHERE created_at >= UNIX_TIMESTAMP(NOW() - INTERVAL 2 DAY)*1000
  AND (title LIKE '%<distinctive phrase 1>%' OR title LIKE '%<phrase 2>%' ...)
ORDER BY created_at DESC LIMIT 30
```
UGC picks already carry their uuid (= news_id) from the MP report.

### 8. Generate 7 PHOTOS — `jack:generate_story_image(aspect="portrait")`
**Gemini renders ONLY the photo now, never the card text** (see the architecture banner in `kc-image-prompt-template.md`). Send a photo-only prompt per slide: one still-life of the subject on dark weathered wood/slate, soft daylight upper-left, slightly desaturated wire-photo look, no people, 1–2 props, **NO text/bands/masthead/panel/stripe**. FMCG: the real brand pack legible (brand IS the subject). Commodity/news: generic, no brands. Order: mandi_bhav = commodity1/2/3, fmcg = fmcg1/2/3, trending_news = news1. Generations occasionally 504 — retry the failed one. `curl` each to `photo_<i>.png` (CDN serves the webp; convert/keep as PNG for the compositor).

### 8b. ⚑ COMPOSITE THE CARDS (mandatory — replaces the old layout-lock + stripe-lock)
The card is now built **deterministically by us**, not by Gemini, so band heights, fonts, type sizes, stripe and text are pixel-identical on every card and every day. Recipe:
1. Place the 7 photos as `photo_1.png … photo_7.png` in the working dir (from Step 8; or crop the photo band from prior art with PIL).
2. Edit the `CARDS` list in **`KC Stories/kc-card-render.py`** with today's 7 cards (label, stripe, headline, price/rep, sub-line + delta, 2 grid rows) and run `PYTHONIOENCODING=utf-8 KC_DIR=<dir> python3 "D:\Kirana Club\Claude Code\KC Stories\kc-card-render.py"` → writes `card_1.png … card_7.png` at 1080×1920 via headless Edge + `Nirmala UI` (shapes Devanagari correctly; PIL can't). **Commodity** = direction colour + tri()+₹ price. **FMCG** = label/stripe/rep/grid per the segment table in Step 5 (arrow ONLY for `fmcg_product_change`; schemes→offer pill, launch→नया pill). **News** = black + `.news` summary.
3. Build a 7-up contact sheet and **Read it** for overall geometry. ⚠ **The contact sheet is NOT enough to catch text↔photo overlap** (tiles are too small — this is how the 2026-06-25 सरसों/सेला overlap shipped). **ALSO Read at full size the card(s) with the MOST text** (longest sub + both grid values wrapping to 2 lines) — that is where the cream-panel content is tallest and most likely to ride up into the photo. Confirm on every card: headline sits fully BELOW the photo's hard cut (no overlap), identical geometry + text sizes, a single flush-left full-height stripe in the direction colour, brands legible on FMCG photos, last grid row clears the bottom CTA, and no oddly-wrapped/clipped text. The compositor is top-anchored (flex-start) precisely to prevent upward overflow — if you ever see the headline over the photo, the content exceeded the panel; re-check the template, don't publish.
4. **Upload** each `card_<i>.png` via `jack:upload_image(blob="news")` → run the `curl` → use THAT url as the slide `img_url`. ⚠ nginx caps uploads at ~1MB → on HTTP 413, resize the PNG to 1000px wide and re-save, then re-upload (the compositor already does this automatically).

**The legacy steps 1–5 below (download → measure → layout-lock → stripe-lock) are RETIRED** — they fought Gemini's text rendering and caused the size/clipping/stripe drift. Kept only as history; do NOT run them. The compositor supersedes both the layout-lock and the stripe-lock.

<details><summary>Retired legacy layout-lock (history only)</summary>
1. **Setup once:** `python3 -m pip install --quiet pillow` (PIL not preinstalled). Work under a temp dir.
2. **Download** all 7 `.webp` via `curl` (the CDN is reachable from the Bash tool even though web_fetch is blocked). Max served res is 768×1376 — that's what the app gets; use it.
3. **Measure + contact sheet:** for each card detect the gold-rule y (masthead bottom) and the cream-panel-top y (scan a column at x≈0.93·W; gold = warm gold pixel, cream = r,g,b all high). Build a 7-up contact sheet and **Read it** to eyeball. Re-roll any card with a missing stripe/gold-rule or a clearly broken render. (Set `PYTHONIOENCODING=utf-8`; don't print Devanagari to cp1252 stdout.)
4. **Layout-lock (no text distortion):** recompose each card on the fixed canvas — masthead kept natural then dark-filled down to a common bottom **M≈215** (on H=1376) with the **4px gold rule at M**; the **photo band vertically scaled** to fill `[M : P]`; the **cream panel copied unscaled** with its top placed at a common **panelTop P≈763** (≈55.4%), cropping/padding only the empty bottom CTA reserve. Photos scale gracefully; masthead and panel text are never distorted. Result: identical masthead-bottom and panel-top on every card → no scroll jump.
4b. **⚑ STRIPE-LOCK (mandatory — generate WITHOUT a stripe, paint it deterministically).** Gemini's stripe is hopeless to control — it drifts in x (flush vs inset), in length (often stops before the bottom), and sometimes doubles. Trying to *detect-and-erase* it failed badly: detection confuses the model's stripe with the body text and either clips the first glyph of each line (ate the क in क्यों) or leaves a second bar. **The fix is to never let Gemini draw a stripe at all:**
   - **Prompt:** the slide prompt explicitly says *do NOT draw any vertical stripe/bar/line/accent; keep the extreme left edge clean empty cream; leave a generous empty left margin (~110/1080 px) before any text.* (See `kc-image-prompt-template.md`.) Result: the raw card's left band is pure cream — nothing to erase.
   - **Lock:** after recompositing, **paint ONE uniform stripe** `x∈[0,14], y∈[P,H]` — flush to the left edge, full cream-panel height to the bottom, fixed 14px, in the **direction colour** (तेज़ी RED `#9A2828` · मंदी GREEN `#1E7A3C` · FMCG/news BLACK `#1A1A1A`). **No detection, no cream-fill** — the clean margin guarantees the 14px bar never overlaps text.
   - **Verify before upload:** confirm (a) the raw left 14px band is cream on every card (no model stripe) and (b) `text_start > 18px` on every card (no clipping). A left-edge contact strip of all cards is the check. Identical width, flush, full-height → uniform on scroll.
5. **Re-upload** each locked PNG via `jack:upload_image(blob="news")` → run the returned `curl` → use THAT url as the slide `img_url`.
</details>

### 9. Generate 3 badges — `jack:generate_story_image(aspect="square")`
Use `kc-badge-template.md` (flat solid thin ring). One per category, strongest visual hook. Strip query params.

### 9b. ⚑ BADGE QC + RING NORMALIZE (mandatory — guarantees identical rings)
⚑ **CURRENT (2026-07-10): the ring + PN are produced deterministically by `kc-badge-banner.py`, NOT hand-normalized.** Feed it the 3 frame-filling `subjfull_<i>.png`; it emits `vD_<i>.png` (entry badge) **and** `badge_pn_<i>.png` (transparent PN) with the finalized ring: **content → thin white ring → RED band flush at the outer edge**, and in the PN the **white ring is cut to transparent**. After running it, QC by MEASURING `max_text_radius ≤ ~438` (white-ring inner ≈454) on every badge so text never grazes the ring, then upload `vD_<i>.png` (Step 11) and `badge_pn_<i>.png` (Step 12). The legacy manual recipe below is history — do NOT hand-crop/redraw the ring.
Prompted ring thickness drifts 6–9% and circle size varies across generations. Composite a deterministic ring:
1. `curl` each badge `.webp` local.
2. Detect circle bbox → centre + radius; **crop interior at ~90% radius** (drops the model's thin ring only), rescale to a **common diameter**. ⚠ Use **90%, not 80%** — since the 2026-07-06 bigger-banner-text rule the headline reaches past 80%r, and an 80% crop clips the bottom banner line. 90% removes the model's ring (which occupies only the outer ~10%r) while keeping all banner text.
3. Redraw an **identical flat ring**: red `#B92B0F` band = **4.5% of diameter**, white separator = **1.5%**, perfectly concentric.
4. Build a contact sheet, **Read it** to confirm uniformity.
5. Re-upload via `jack:upload_image(blob="news")` → use THAT url in Step 11.

### 10. Refresh + publish each tag (AUTO)
Per tag: `jack:draft_story_refresh(tag, slides=[{news_id, img_url}, ...])` → `jack:preview_story(payload)` → `jack:update_story(story_id, payload, confirm=True, confirmation_token=<token>, actor_name="Harsh Shrivastava")`. Use the **layout-locked** slide URLs from Step 8b.
- `draft_story_refresh` preserves CTA text/colours, durations, status, and validity windows — only image + news_id change. Story stays `published` → goes live on update.
- `actor_name` = the operator running it (default **Harsh Shrivastava**; the signed-in Google account is shared, so always pass actor_name).
- If a write returns "No approval received", the operator hasn't set client "Allow always" yet — surface that once, then the operator approves and it flows.

### 11. Swap the 3 badges
`jack:update_story_entry_badges(updates=[{img_url, story_id}, ...], confirm=False)` → returns match plan + token → call again `confirm=True, confirmation_token=<token>, actor_name="Harsh Shrivastava"`. Match by `story_id`. Use the **normalized** badge URLs from Step 9b.

### 12. Build the push payload (`multi_icon_stories` `notification_data`)
> This JSON is no longer pasted by a human — it is the `--nd` input to the scheduler in **Step 12b**.
⚑ **The PN uses a SEPARATE transparent export of each badge, NOT the white-bg widget badge** (operator rule, 2026-06-25). The in-app entry-widget badges (Step 11) stay the normalized 1080² square (white bg). For the push, use the **`badge_pn_<i>.png`** files that **`kc-badge-banner.py` now emits automatically** alongside each `vD_<i>.png` (2026-07-10) — a **SQUARE (1:1) 500×500 RGBA** transparent export built with a **compound alpha mask**: the content disc + the red band are opaque, and the **inner white ring between them is cut to TRANSPARENT** (so the push bg shows through), with **red as the outermost ring flush at the edge** — matching the entry-badge ring exactly. No separate/manual masking step: the compositor keeps the PN in lockstep with the ring geometry, so `sep_w`/`red_w`/FS changes flow through to the PN too. Verify alpha on a checkerboard, then `upload_image(blob="news")` each. The CDN webp keeps the alpha (verify `mode=RGBA`). Use **these transparent square URLs** in the push `url` (clean `.webp`); keep the **fixed deep_links unchanged** (each opens its reel; story_ids are permanent — never re-encode). Order = 1 mandi, 2 fmcg, 3 tn.
```json
{
  "images": [
    {"url": "<mandi badge .webp>", "deep_link": "kc://custom?screen=WebViewOld&params=ewAiAHMAYwByAGUAZQBuAFQAaQB0AGwAZQAiADoAIgAiACwAIgBzAGgAbwB3AEgAZQBhAGQAZQByACIAOgBmAGEAbABzAGUALAAiAHUAcgBpACIAOgAiAGgAdAB0AHAAcwA6AC8ALwB3AGUAYgBhAHAAcABzAC4AcgBlAHQAYQBpAGwAcAB1AGwAcwBlAC4AYQBpAC8AcwB0AG8AcgBpAGUAcwA%2FAHMAdABvAHIAeQBfAGkAZAA9ADUAMQBmADcAZQBmAGIAOAAtADgAZAAzAGYALQA0AGUAMgAxAC0AYQA2ADMAYgAtADUANgAxADUAMQAzADAANgA0ADcAOABjACIAfQA%3D&campaign_tags=multi_icon_stories", "name": "mandi"},
    {"url": "<fmcg badge .webp>", "deep_link": "kc://custom?screen=WebViewOld&params=ewAiAHMAYwByAGUAZQBuAFQAaQB0AGwAZQAiADoAIgAiACwAIgBzAGgAbwB3AEgAZQBhAGQAZQByACIAOgBmAGEAbABzAGUALAAiAHUAcgBpACIAOgAiAGgAdAB0AHAAcwA6AC8ALwB3AGUAYgBhAHAAcABzAC4AcgBlAHQAYQBpAGwAcAB1AGwAcwBlAC4AYQBpAC8AcwB0AG8AcgBpAGUAcwA%2FAHMAdABvAHIAeQBfAGkAZAA9AGEAOQAzAGUAMwA0AGEAYgAtADMAYQA4AGMALQA0AGMAYgBlAC0AYgA3AGQAZQAtADYANAAyAGUANABiADUAMABlADQAYgAyACIAfQA%3D&campaign_tags=multi_icon_stories", "name": "fmcg"},
    {"url": "<tn badge .webp>", "deep_link": "kc://custom?screen=WebViewOld&params=ewAiAHMAYwByAGUAZQBuAFQAaQB0AGwAZQAiADoAIgAiACwAIgBzAGgAbwB3AEgAZQBhAGQAZQByACIAOgBmAGEAbABzAGUALAAiAHUAcgBpACIAOgAiAGgAdAB0AHAAcwA6AC8ALwB3AGUAYgBhAHAAcABzAC4AcgBlAHQAYQBpAGwAcAB1AGwAcwBlAC4AYQBpAC8AcwB0AG8AcgBpAGUAcwA%2FAHMAdABvAHIAeQBfAGkAZAA9ADEANgBjADkAZQBhAGEAZQAtADMAYwAzAGUALQA0ADcAZgBmAC0AOQAwADMAMAAtADQAYgA0ADMANgAyADQAOQA5ADAANAA1ACIAfQA%3D&campaign_tags=multi_icon_stories", "name": "tn"}
  ],
  "show_dismiss_button": false,
  "dismiss_button_text": "हटाए",
  "dismiss_after": 960
}
```

### 12b. ⚑ SCHEDULE THE PUSH AUTOMATICALLY — daily 16:30 IST (operator, 2026-08-13)
**SUPERSEDES the old manual-paste process and the retired journey design.** The run no longer just
prints JSON for a human — it **creates and schedules a fresh `multi_icon` one-time campaign every day**
via `pn-schedule.py`, using the audience + fixed key-values in `specs/pn-campaign-registry.json`.

```bash
# write today's Step-12 JSON (3 badge_pn URLs + the FIXED deep_links) to a file, then:
python3 pn-schedule.py --type kc_stories_multi_icon --nd /tmp/nd_stories.json \
        --time "<TODAY> 16:30" --send
```
Returns `{"campaign_id": "...", "license_code": "in~58adcc4a"}`. Record the campaign_id.

**🚨 HARD PRECONDITION — the recurring campaign `~1dng34j` MUST be paused/stopped first.**
It is a RECURRING campaign that fires on its own. If it is still active while this step schedules a
daily one-time campaign, **every user gets the Stories push TWICE**. Verify it is paused before the
first automated run, and never re-activate it.

**Gates (all mandatory):**
- **Only schedule if the stories actually published** (Steps 10 + 11 succeeded). Never send a push
  pointing at stale or half-updated stories.
- **Lead time:** `pn-schedule.py` refuses anything under 45 min out. If the run is so late that 16:30
  today is inside that window, **DO NOT shift the time and DO NOT send** — skip, and flag it loudly in
  the summary for the operator. Never silently move the send time.
- **NEVER retry on failure.** A non-200 from the pipeline does **not** mean "not sent" — the campaign
  is created+activated *before* the call can fail (production: Samachar 242/242 rows with NULL
  campaign_id). On error, report it and stop. There is no cancel API; a retry double-sends.
- **Idempotency** is enforced by `pn-schedule-log.json` (key = `type|time`). Commit it with the ledger
  in Step 13 so the guard survives the ephemeral container.

**Known, accepted deltas vs the old hand-built `~1dng34j`** (measured 2026-08-13 — do not treat as bugs):
- The pipeline force-adds 2 exclusions (`~48clbl2` Experimentation Segment, `~1i5j875` New Users D0-D2).
  Stories previously excluded nothing, so reach drops ~1–2%. Not disableable — see
  `pn-automation-ticket.md` item 4b.
- Container changes RECURRING → daily ONE-TIME (one campaign per day, fresh id).
- `campaignType` is forced to an **unmapped** value (`Others`) so the create cannot silently rewrite
  journey campaigns. **Never** change this to a mapped type (Samachar/Rujhan/…).
- `isSticky` stays **false** and no CTA is set — this is what keeps the 3 per-badge `deep_link`s working
  (`~1dng34j` deliberately has an EMPTY on-click action). Adding any CTA breaks badge routing.

### 12c. Report the scheduled push (NO Slack DM)
The push JSON is no longer a deliverable for a human to paste. Report the **campaign_id + edit URL** so
the operator can spot-check or kill it:
`https://in.webengage.com/accounts/in~58adcc4a/push-notifications/campaigns/<campaign_id>/message`
**Do NOT send any Slack DM** (operator Harsh, 2026-08-17: the Hritik/Harsh DM was for testing and is now
retired — just put the edit URL in the run report every time). The old weekend-only JSON handoff is also
**retired** (there is nothing left to paste).

### 13. ⚑ WRITE THE LEDGER (mandatory — this is what stops tomorrow's repeats)
Immediately after the badges publish, append today's run to `KC Stories/used-picks-log.json`: a new `runs[]` entry with today's `date` and the **final published** `news_id` per tag under `picks` (mandi_bhav / fmcg / trending_news), plus any pick that was shown then swapped out under `also_shown`. Keep newest last; never delete history. Skipping this re-breaks dedup, so do it before the summary. (If the file was missing, create it with `dedup_window_days: 12`, `brand_dedup_window_days: 7`, and this single run.)
- **⚑ Every pick and `also_shown` entry MUST carry a normalized `brand` token** (lowercase product-line, e.g. `oral-b`, `close-up`, `navratna`, `colgate`) alongside its `news_id` + `label` — this is what makes tomorrow's **brand-level dedup (Step 3)** deterministic instead of an eyeball check. For commodity/news use the commodity/subject as the token (e.g. `arhar`, `haldi`, `pyaaz`) — optional but recommended. Ensure the file has top-level `brand_dedup_window_days: 7` (add it if missing).

### 14. Post-publish summary (not a gate)
Output: picks table (story · direction · LR · id), what was swapped/skipped + any LR↔body mismatch flagged for eng, the 7 slide image links + 3 badge links for spot-check (plus the QC contact sheets if regenerated), and the **scheduled push**: `campaign_id`, send time (16:30 IST), and the one-tap edit URL
`https://in.webengage.com/accounts/in~58adcc4a/push-notifications/campaigns/<campaign_id>/message`.
If the push was **skipped** (publish failed, lead-time gate, or a non-200 from the pipeline), say so at the
TOP of the summary with what the operator must do — for a non-200, that the campaign may still be live
and must be checked in the dashboard rather than re-run. Note: anything off is one tap to edit/remove on
the D2R dashboard.

---

## EDITORIAL VOICE
- Hindi (Devanagari) for all visible card text. Headlines 2–5 words; sub-headlines ≤12 words.
- "क्या करें" = operational guidance ("पुराने स्टॉक पर पुराना MRP बेच लें"). "क्यों" = factual reason.
- Bloomberg/Economist tone. NEVER "Hurry/Sale/Offer/Free", no exclamation marks, no promotional language. Extract real numbers.
- तेज़ी = RED #9A2828 (bad for shopkeeper) · मंदी = GREEN #1E7A3C (good) · FMCG & news = BLACK #1A1A1A.

## SKIP-ALWAYS
Gold/silver (सोना/चांदी) · **hyper-local** schemes (single city/distributor only — but Retailer/Consumer Scheme are otherwise VALID FMCG segments now, not a blanket skip) · vague no-number posts · scam/fraud/arrest news bait · same brand+product as dedup set · **FMCG brand/product-line featured in the last 7 days — ENFORCED, not soft, via the ledger `brand` field + `brand_dedup_window_days` (see Step 3 brand-level dedup); auto-swap, never publish a brand that recurs inside the window even under a new news_id** · posts with no brand + no price + no weight + no launch + no scheme.
Soft (not a hard skip): avoid 3+ consecutive days dominated by the same FMCG **category** (e.g. oral-care toothpaste/brush) — spread across categories (oral-care · detergent/soap · food/candy · personal-care) when Like Rate allows.

## TOOL GOTCHAS
- Birbal: re-establish codebase context before every `query_db`.
- `new_kiranaclubdb` (`stories`, `story_items`) is NOT reachable via Birbal — only `main` + `community`. Use `jack:get_story` for live story state.
- Strip CDN query params from all image URLs (clean `.webp`).
- **QC images by downloading, not web_fetch:** `images.kiranaclub.ai` is blocked for `web_fetch`, but the **Bash tool `curl` CAN reach it** — download `.webp`, convert/inspect with PIL, build contact sheets, and `Read` them. This is how Steps 8b/9b verify consistency. CDN serves max 768×1376 for portrait, 1024×1024 for square.
- **PIL not preinstalled:** `python3 -m pip install --quiet pillow` once. No `raqm` → cannot shape Devanagari, so never re-render Hindi text locally; only reposition/scale existing bands.
- **upload_image:** `jack:upload_image(file_path, blob="news")` returns a `curl` one-liner; run it in Bash, stdout is the CDN URL (plain text).
- jack write tools each need their own client "Allow always"; `update_story` and `update_story_entry_badges` are separate permissions.

## MID-CHAT RULE CHANGES
If a chat decision changes a rule, apply it for the session AND remind at the end: "Update `<file>` to make this permanent: change `<X>` to `<Y>`."
