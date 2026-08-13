# ROUTINE PROMPT — required edits (2026-08-13)

The KC Stories scheduled-routine prompt lives in the Claude Code schedule config (NOT in this repo and
NOT editable from inside a run). After the 2026-08-13 change that auto-schedules the WebEngage push,
three blocks of that stored prompt are stale and contradict `kc-stories-workflow.md`.

Specs win on conflict, so a run would still behave correctly — but the stale blocks tell the routine to
produce a deliverable that no longer exists (the hand-paste JSON) and to do a weekend Slack handoff for
it. Replace them.

---

## EDIT 1 — replace the whole WEEKEND HANDOFF block

**DELETE this block** (starts `===== WEEKEND WEBENGAGE HANDOFF`, ends `...do NOT send the handoff.`)

**REPLACE WITH:**

```
===== SCHEDULE THE WEBENGAGE PUSH (daily, automatic - Step 12b) =====
The push is no longer pasted by a human. After the stories + badges are live, BUILD today's
multi_icon notification_data (3 badge_pn URLs + the FIXED deep_links, order mandi/fmcg/tn), write it
to a file, and SCHEDULE it for 16:30 IST today:
  python3 pn-schedule.py --type kc_stories_multi_icon --nd /tmp/nd_stories.json --time "<TODAY> 16:30" --send
Record the returned campaign_id. Commit pn-schedule-log.json together with the ledger.
GATES (all mandatory):
- Only schedule if the stories ACTUALLY published. Never push to stale/half-updated stories.
- The script refuses <45 min lead. If 16:30 today is inside that window, DO NOT shift the time and DO
  NOT send - skip it and flag LOUDLY at the top of the report.
- NEVER retry on failure. A non-200 does NOT mean "not sent" (the campaign is created+activated before
  the call can fail). Report it, stop, and tell the operator to check the dashboard - there is no
  cancel API and a retry double-sends.
- If Slack is available, DM the campaign edit URL (one line) to Hritik U057QBHF43H and Harsh
  U09K92G1U1X. If Slack is unavailable, skip and report - never fail the run.
The old weekend-only JSON handoff is RETIRED - there is nothing left to paste.
```

## EDIT 2 — replace the FINAL OUTPUT block

**DELETE:** `the WebEngage multi_icon_stories push JSON (today's 3 badge URLs swapped into url, the
fixed deep_links unchanged, order mandi/fmcg/tn), whether the weekend Slack-to-Hritik handoff was SENT
(Sat/Sun) or SKIPPED (weekday), and`

**REPLACE WITH:** `the SCHEDULED PUSH (campaign_id, send time 16:30 IST, and the edit URL
https://in.webengage.com/accounts/in~58adcc4a/push-notifications/campaigns/<campaign_id>/message) - or,
if it was skipped, say so at the TOP with the reason and what the operator must do, and`

## EDIT 3 — PIPELINE SUMMARY line

**FIND:** `PUBLISH via jack: update_story (the slides into the 3 tags) + update_story_entry_badges (the
3 badge URLs). actor_name='Harsh Shrivastava'.`

**APPEND:** ` THEN schedule the multi_icon push for 16:30 IST via pn-schedule.py (Step 12b).`

Also add `pn-schedule.py` and `specs/pn-campaign-registry.json` to the root-files list near the top.

---

## 🚨 ONE-TIME OPERATOR ACTION (before the first automated run)

**Pause / stop the recurring WebEngage campaign `~1dng34j`.** It fires on its own schedule. If it is
still active while the routine schedules a daily one-time campaign, **every user gets the Stories push
twice.** This cannot be done from a run — it is a dashboard action.
