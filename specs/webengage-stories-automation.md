# KC STORIES → WEBENGAGE PUSH (AUTOMATION DESIGN)

> ⛔ **THE OLD JOURNEY DESIGN IS DEAD — DO NOT BUILD IT.** Superseded 2026-08-13 after a full
> code recon of the real pipeline. The previous version of this doc claimed *"WebEngage has no API
> to edit a campaign's content"* and therefore specced a custom-event + Journey + REST-API-key
> design. **That premise was wrong.** A create+schedule+activate API is already in production and
> already reachable from the existing d2r stack. Do NOT build the journey, do NOT provision
> `WEBENGAGE_API_KEY`, do NOT fire `kc_stories_daily_refresh`.
>
> ⏸ **Current status: still MANUAL.** The daily run outputs the ready-to-paste `notification_data`
> JSON and the operator pastes it into campaign `~1dng34j`. Keep doing that until the ticket in
> `pn-automation-ticket.md` ships. **Do NOT attempt any automated WebEngage write until then.**

---

## THE REAL PIPELINE (verified in code, 2026-08-13)

```
caller ──POST──> kc.retailpulse.ai/api/newsUpload            (d2r-dashboard-BE)
                   └─> scheduleWebengageNotification.js
                        └─POST─> asia-south1-op-d2r.cloudfunctions.net/d2r_notification_automation
                                   ├─ POST /v2/accounts/{lc}/push-notifications          (create)
                                   ├─ POST /v1/.../{id}/targetingRule/schedule           (schedule)
                                   └─ PUT  /v1/.../{id}/activate                         (launch)
```

`jack create_push_notification` and the 8-daily-post `postAutomation` are **both thin wrappers on
this same pipe** — they are not separate systems.

### What the pipe supports
| Capability | Status | Evidence |
|---|---|---|
| `includedSegments` / `excludedSegments` + operators | ✅ | `utils.py:522-525`; flat array of WebEngage encodedIds `["~26o88jj","bifek4"]` |
| Arbitrary `kvPairs` → WebEngage `custom_keys` | ✅ **zero validation** | `utils.py:536-537, 555-559` |
| Custom templates via `template_type` + `notification_data` | ✅ proven | 851 live `duo_image` payloads in `community.webengage_notification_history` |
| Create + schedule + activate | ✅ | above |
| **Update / clone / GET / cancel / delete a campaign** | ❌ | no `campaign_id` input field exists |
| **Recurring campaigns** | ❌ | `container:"ONETIME"` hardcoded at all 3 call sites |

### What jack does NOT expose (the gap)
`jack create_push_notification` takes only `seller` / `generic_screen_name` /
`scheduled_time_epoch_ms` / `variations`. **No cohort parameter. No kvPairs passthrough.** It is a
broadcast relay. The cohort control the operator relies on when manually copying a campaign exists
in the pipe but is not reachable through jack today.

⚠️ `jack list_cohorts` (253 names) is the **wrong namespace** — those are Firestore/coupon cohorts.
WebEngage PN targeting uses opaque encodedIds (`~23db83k`). Three disjoint namespaces; never map by name.

---

## ⚑ LANDMINES (any implementation MUST handle these)

1. **Journey fan-out.** Every successful create *also* PUTs the new variations over every journey
   campaign mapped to that `campaignType` (`utils.py:409` → `CAMPAIGN_TYPE_ID_MAPPING`; Samachar = 17
   IDs). → **Use a campaignType that is NOT in that map** (`Others`, or a new `KC Stories` string) and
   never register it there.
2. **Success signal is broken.** The journey PUT runs *after* create+schedule+activate and uses a bare
   `assert status==201` (`utils.py:160`). Any failure → HTTP 500 **while the campaign is already live**;
   caller stores `campaign_id = NULL` and reports no error. Production: **Samachar 242/242 rows NULL**.
   → **NEVER auto-retry.** A retry double-sends to the full cohort. Alert a human instead.
3. **Sticky breaks per-badge deeplinks.** `MultiIconRenderer.kt:181-184` resolves each tap as
   `campaignCTA ?: deep_link` — the CTA wins. `isSticky=true` injects a NewsDetail CTA (badge 2 goes
   wrong); a prime CTA collapses **all three** onto one destination.
   → **`isSticky=false`, omit `stickyDetails`.**
4. **Badge pixel size.** `MultiIconRenderer` decodes with **no size cap** (unlike DuoImageRenderer).
   3 × 1080² ARGB ≈ 14 MB vs a ~1 MB Binder limit → `notify()` throws, exception swallowed, campaign
   reports "sent", user sees nothing. **File size is irrelevant — decoded pixels are what matter.**
   → target ~**300×300 px** (layout displays 120dp expanded / 48dp collapsed).
   ⚠️ **Unresolved tension:** today's manual PN ships 500×500 badges and is believed to render. Verify
   on a real device before changing anything — do not "fix" a working size on theory alone.
5. **`notification_data` must be a STRINGIFIED JSON string.** An object silently degrades to a plain
   text push. (`MultiIconRenderer.kt:90-97` does `JSONObject(getString(...))`.)
6. **Neither `multi_icon` nor `duo_image` renders title/message.** Copy must be baked into the image
   pixels. `titles[]`/`messages[]` are required by the API but render nowhere — pass short ballast.
7. **No dedupe anywhere.** Duplicate live campaigns already occurred in production (2026-07-09:
   `government schemes` created twice, both live). → the caller must own idempotency
   (`UNIQUE(run_date)` insert-before-create).
8. **`multi_icon` has never been sent through this function** (0 rows). It is proven only in the
   hand-built campaign `~1dng34j`. First automated send must be to an internal test cohort.

---

## TARGET DESIGN (once the ticket ships)

**Option 1 — update recurring `~1dng34j` in place: REJECTED.** The only variations-PUT is a hardcoded
side effect of a create, so "updating" would still create a throwaway campaign daily *and* require
adding `~1dng34j` to the journey map (landmine 1).

**Option 2 — fresh one-time campaign daily: ADOPTED.**
- `campaignType` = unmapped literal · `isSticky=false` · `sendNow=false` · explicit `scheduledTime`
- `kvPairs = {template_type:"multi_icon", notification_data:"<JSON STRING>", we_custom_render:true}`
- `notification_data.images` = 3 × `{url, deep_link, name}` — badge URLs fresh daily, **deep_links are
  the permanent fixed ones** (story_ids never change; see `kc-stories-workflow.md` Step 12)
- cohort = the exported `~1dng34j` audience (see blocker below)
- idempotency row keyed on run_date, written **before** the create call

---

## 🚧 BLOCKING PREREQUISITES (operator — before engineering starts)

1. **Export `~1dng34j`'s full config from the WebEngage UI.** It appears in **0 of 19,497**
   `webengage_notification_history` rows — no KC system can read it. A fresh API campaign *hardcodes*
   `applyFrequencyCapping=true`, `applyDnd=true`, `ttl=4h`, Android-only, and force-adds 2 holdout
   segments (`EXP_SEGMENT`). **That inheritance is exactly what "copy the campaign" was silently
   preserving.** Capture: container/recurrence, segment inclusion+exclusion DTOs with operators,
   frequency capping, DND, TTL, sendInTz, conversion goal, control-group %, layoutEId, iOS flag,
   and whether a prime CTA exists. This is the acceptance target.
2. **Confirm the 3 badge→story_id mapping** and that each story passes its own `audience` gate.
3. **Decide sticky.** If the live campaign is sticky today, per-badge routing already differs from
   what Option 2 will produce.

## SECURITY (flag to tech separately)
The cloud function is **completely unauthenticated** and the WebEngage bearer token is a **committed
literal**. Anyone with the URL can push to the entire Android base. Not caused by this work, but this
work increases traffic through it.

---
Full engineering scope: **`specs/pn-automation-ticket.md`**.
