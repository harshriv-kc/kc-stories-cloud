# TICKET — Expose cohort + custom-template PN scheduling (image PN & KC Stories)

**Owner:** notifications / d2r backend · **Requested by:** Harsh Shrivastava
**Context doc:** `specs/webengage-stories-automation.md` (read the LANDMINES section first)

## Goal
Let an automated caller schedule a WebEngage push with (a) an explicit include/exclude cohort and
(b) a custom render template (`duo_image` / `multi_icon`) whose images change every run — without a
human copying a campaign in the WebEngage UI.

## Why this is small
The pipe **already supports all of it**. `d2r_notification_automation` accepts `segments.*` and
arbitrary `kvPairs` with zero validation, and `duo_image` via `kvPairs` is proven in production (851
payloads). Nothing new needs to be invented — the capability just isn't reachable from an automated
caller safely.

---

## Scope

### 1. Entry point that accepts cohort + kvPairs
Expose a route (or extend the existing internal one) accepting:

```jsonc
{
  "campaignName": "KC Stories — 2026-08-14",
  "campaignType": "KC Stories",        // MUST NOT be added to CAMPAIGN_TYPE_ID_MAPPING
  "campaignTags": ["Stories"],
  "scheduledTime": 1786593238,          // epoch seconds, IST
  "sendNow": false,
  "launchNotification": true,
  "isSticky": false,                    // REQUIRED false — see landmine 3
  "titles": ["KC Stories"],             // ballast; renders nowhere
  "messages": ["आज की खबरें"],
  "segments": {
    "includedSegments": ["~26o88jj"],
    "excludedSegments": ["~23db83k"],
    "includedSegmentsOperator": "OR",
    "excludedSegmentsOperator": "OR"
  },
  "kvPairs": {
    "template_type": "multi_icon",
    "we_custom_render": true,
    "notification_data": "{\"images\":[…]}"   // STRING, not object — see landmine 5
  },
  "idempotency_key": "kc-stories-2026-08-14"
}
```

### 2. `skipJourneyUpdate` flag (safety-critical)
Add a request field that bypasses `update_journey_message` (`utils.py:409`). Today every create also
PUTs its variations over **up to 17 unrelated live journey campaigns** selected purely by the
`campaignType` string. Using an unmapped campaignType avoids it, but the blast radius is one typo
away. Default `false` to preserve current behaviour; automation sends `true`.

### 3. Fix the false-failure path
`update_journey_message` runs **after** create+schedule+activate and `send_post` uses a bare
`assert res.status_code == 201` (`utils.py:160`). Result: HTTP 500 returned **while the campaign is
already live**, `campaign_id` stored NULL, no error surfaced. Production evidence:
`Samachar 242/242` and `Rujhan 228/232` rows have NULL `campaign_id`.

- wrap `update_journey_message` in try/except so it can never poison the return
- replace bare asserts with status checks returning a structured error
- **always return the `campaign_id` already obtained**, even on partial failure

### 4. Server-side payload validation (cheapest high-value guard)
Reject the request unless:
- `typeof kvPairs.notification_data === "string"` **and** `JSON.parse` succeeds
- for `multi_icon`: `parsed.images` is a non-empty array, ≤3 items, each with a non-empty `url`
- for `multi_icon`: `isSticky !== true`
- every `includedSegments`/`excludedSegments` entry resolves in the segment list
  (today unknown IDs **silently fall through to userListIds** — `utils.py:140-141`)

### 4b. Make the forced experiment holdouts overridable (`skipExpSegment`)
`utils.py:286` unconditionally prepends `EXP_SEGMENT = ['~48clbl2','~1i5j875']`
(constants.py:18) to the caller's exclusions, with no way to opt out:
```python
excluded_segments_combined = EXP_SEGMENT + data['excludedSegments']
```
**Measured live 2026-08-13:** an automated Scheme/FMCG campaign came out at 201,619 reachable
vs 205,286 for the hand-built one — identical in every other respect. Only difference: those 2.

Add an optional `skipExpSegment: true` request flag (default false, preserving today's behaviour).
Also **dedupe** `excluded_segments_combined` — a caller who legitimately lists one of those two
(the YouTube campaign does) currently sends it twice, and there is no dedup in
`separate_segments_by_type`.

Note: this is only needed if the operator wants automated campaigns to match hand-built ones that
do NOT exclude the holdouts. The cheaper fix is to add the 2 exclusions to those manual campaigns —
every pipeline-created PN already excludes them.

### 5. Idempotency
No dedupe exists at any layer; duplicate live campaigns already shipped (2026-07-09,
`government schemes` created twice, both with real campaign_ids). Add a `UNIQUE(idempotency_key)`
(or `UNIQUE(run_date, campaign_type)`) table written **before** the create call.

---

## Acceptance criteria
1. A call with an explicit include+exclude cohort produces a campaign whose targeting matches the
   exported `~1dng34j` config field-for-field (see prerequisite below).
2. `multi_icon` with 3 images renders on a real device and **each badge opens a different story**.
3. Re-running the same `idempotency_key` creates **no** second campaign.
4. A forced journey-PUT failure still returns a valid `campaign_id` and a clear error field.
5. No campaign other than the intended one is modified by the call (verify against
   `CAMPAIGN_TYPE_ID_MAPPING`).

## Out of scope
Recurring campaigns (`container:"ONETIME"` is hardcoded; not needed — Option 2 creates one campaign
per day). Campaign update/clone/delete (no such API exists).

---

## ⚠️ Notes for whoever picks this up
- **Never auto-retry a failed create** until item 3 lands — the campaign may already be live.
- `multi_icon` has **never been sent through this function** (0 rows in
  `webengage_notification_history`). First automated send must target an internal test cohort.
- `MultiIconRenderer` decodes bitmaps with **no size cap** (unlike `DuoImageRenderer`, which uses
  `decodeBitmapUnderLimit`). Oversized badges → `notify()` throws → silent no-notification. Consider a
  one-line renderer fix reusing `decodeBitmapUnderLimit`. Verify current 500×500 badges on a device
  before changing the generator.
- **Security, pre-existing but relevant:** `d2r_notification_automation` is completely
  unauthenticated and the WebEngage bearer token is a committed literal. Anyone with the URL can push
  to the entire Android base. Worth a separate ticket.

## Blocking prerequisite (operator)
Export `~1dng34j`'s full WebEngage config — it exists in **0 of 19,497** history rows, so nothing in
KC can read what the current push is actually configured as. Without it there is no acceptance target
and the automated campaign may silently under-deliver (fresh campaigns hardcode frequency capping,
DND, 4h TTL, Android-only, plus 2 forced holdout segments).
