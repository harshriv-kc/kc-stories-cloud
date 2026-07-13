> ⏸ **ON HOLD (operator, 2026-06-25):** not building this yet. For now the daily run just outputs the ready-to-paste `notification_data` JSON (transparent badge URLs) and the operator enters it in WebEngage manually for a few days. This doc is the design to resume later — do NOT attempt any WebEngage write until the operator says go.

# KC STORIES → WEBENGAGE PUSH (UNATTENDED, EVENT-TRIGGERED)

Goal: the daily cron pushes the fresh stories multi_icon notification **without anyone opening the WebEngage editor**. WebEngage has no API to edit a campaign's content, so instead of editing the manual campaign `~1dng34j`, we drive a **Journey triggered by a custom event** whose push content is personalized from the event's attributes. The cron fires that event each day with the 3 transparent badge URLs.

## Why not the old way
- The campaign editor is an internal SPA with no public state/API (confirmed). A headless cron has no logged-in browser to type into.
- jack `create_push_notification` / hedwig only support text/image/timer templates — NOT `multi_icon`. So the push can't be created via our MCP tools either.
- WebEngage's supported lever for dynamic content sent unattended = **REST Events API + a journey personalized from event attributes.**

## Endpoint (India DC)
```
POST https://api.in.webengage.com/v1/accounts/in~58adcc4a/events
Authorization: Bearer <WEBENGAGE_API_KEY>     # stored as a cron/env SECRET, never in code or chat
Content-Type: application/json
x-request-id: <hex>                            # optional, for idempotency
Body: {"userId": "<uid>", "eventName": "kc_stories_daily_refresh",
       "eventTime": "<ISO8601 ±hhmm>", "eventData": {"mandi_url": "...", "fmcg_url": "...", "tn_url": "..."}}
```
Limits: attr string ≤1000 chars (URLs ~95, fine) · ≤25 attrs/event · event name ≤50 chars, no `we_` prefix · 5000 req/min.
Credentials live at **Data Platform > Integrations > REST API** (Account Admin only).

## ONE-TIME setup (operator, in WebEngage UI — cannot be done via API)
1. **Custom event:** Data Platform > Data Management > Custom Events → define `kc_stories_daily_refresh` with attributes `mandi_url`, `fmcg_url`, `tn_url`; tick **"Enable use in Personalization."**
2. **Journey:** Trigger = custom event `kc_stories_daily_refresh`. (Optionally AND a segment to bound the audience.) Add a **Send Push** block configured exactly like campaign `~1dng34j`: `template_type=multi_icon`, `we_custom_render=true`, `dismiss_after=960`, `campaign_tags=['Stories']`, button label `हटाएं`, on-click "Dismiss". In the `notification_data` key-value, paste the JSON below with the **3 image URLs as personalization tokens** and the **deep_links hardcoded** (they're permanent):
   ```json
   {"images":[
     {"url":"{{event.kc_stories_daily_refresh.mandi_url}}","deep_link":"<FIXED mandi deep_link>","name":"mandi"},
     {"url":"{{event.kc_stories_daily_refresh.fmcg_url}}","deep_link":"<FIXED fmcg deep_link>","name":"fmcg"},
     {"url":"{{event.kc_stories_daily_refresh.tn_url}}","deep_link":"<FIXED tn deep_link>","name":"tn"}
   ],"show_dismiss_button":false,"dismiss_button_text":"हटाएं","dismiss_after":960}
   ```
   (The 3 fixed deep_links are the permanent ones in `kc-stories-workflow.md` Step 12 — story_ids never change.)
3. Generate the **REST API key**, hand it to the cron as the secret env var `WEBENGAGE_API_KEY` (NOT pasted in chat / not committed).

## Cron behavior (added to the daily run, after badges publish)
- Compute the 3 transparent 230×400 PN badge `.webp` URLs (Step 12 already produces them). ⚠ Build the ring red-to-edge (solid red disc → white separator → photo on top, then downscale for AA); do NOT alpha-cut the white-bg square badge or a ~1px white ring shows outside the red on the grey PN bg (fixed 2026-06-25).
- Fire `kc_stories_daily_refresh` via the Events API for the chosen audience (see "Audience" — userIds sourced from the community DB), eventData = the 3 URLs. Batch within the 5000 req/min limit; retry on 5xx; use `x-request-id` per call for idempotency.
- **Gated:** if `WEBENGAGE_API_KEY` is unset (not yet configured), SKIP this step and report it in the run summary (per the operator's "publish what it can, report the rest" rule) — do not fail the run.
- Helper: `KC Stories/we_fire_event.py` (reads `WEBENGAGE_API_KEY` from env; args = license, event name, the 3 URLs, and a userIds source).

## Audience (TO CONFIRM with operator)
Event-triggered journeys send to whoever the event was fired for (optionally further filtered by a segment in the journey). Decide the daily userId set the cron fires for: whole active base / a recency segment / pilot first. The cron enumerates those userIds from the community `users` table.

## Status
- [x] Daily run generates the transparent badges + exact JSON (live).
- [ ] Operator: build the custom event + journey, provide `WEBENGAGE_API_KEY` secret, confirm audience.
- [ ] Then enable the cron event-fire step.
