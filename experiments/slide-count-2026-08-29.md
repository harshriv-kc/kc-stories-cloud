# EXPERIMENT — KC Stories dynamic slide-count (Phase 1)

**Status:** ACTIVE · **Owner:** operator U09K92G1U1X (Harsh) · **Set up:** 2026-08-28
**Window (5 runs):** 2026-08-29 → 2026-09-02 · **Conclusion DM:** day-5 (2026-09-02) · **Decision handled:** day-6 (2026-09-03)

The daily routine reads this file whenever `kc-stories-workflow.md` points here. During the window it **overrides the base slide count** in workflow §5. Everything else in the pipeline is unchanged. If this file is absent or the window has passed, ignore and run the base pipeline.

---

## Hypothesis
Adding a 4th slide to Mandi and/or FMCG **when a genuinely high-quality 4th post exists** grows content consumption **without** hurting entry, completion, or next-day return. If it hurts any of those, revert to base.

## What changes during the window (the ONLY change)
- **Mandi** and **FMCG** may publish **4 slides** instead of 3 — but a 4th is added **only if** it passes §6 body-verify (concrete ₹ number) **AND** its LR ≥ that bucket's trailing-7-day median LR. Otherwise stay at 3. **Never pad with a weak/no-number 4th** (SKIP-ALWAYS still binds).
- **News stays 1** (news-source discipline is a separate future experiment — do not change it here, to keep this read clean).
- So a day can be 3+3+1 (no qualifying 4th) or up to 4+4+1. The log records which and why.
- All dedup (news_id 12d + brand 7d), QC, badge, PN, and ledger steps are **unchanged**. PN stays the fixed 3 icons.

## Per-day logging (every run in the window)
After publishing, append one object to `experiment-slide-count-log.json → days[]`:
```
{ "date": "YYYY-MM-DD",
  "mandi_slides": 3|4, "fmcg_slides": 3|4, "news_slides": 1,
  "mandi_4th": {"news_id","brand","LR","bucket_median_LR"} | null,
  "fmcg_4th":  {"news_id","brand","LR","bucket_median_LR"} | null,
  "reason": "why 3 or 4 per bucket (LR vs median, or no qualifying 4th)",
  "metrics_asof": "<last fully-baked date pulled>",
  "metrics": { ...the snapshot below... } }
```
Pull the metric snapshot for the **previous** (fully-baked) day so numbers are stable.

## Metrics — Mixpanel project **2551336** (events already live)
Story events: **Story Viewed** (props: `position` = slide index, `tag` = bucket, `story_id`, `$user_id`), **Story CTA Click** (same props), **Story Closed**. Rail: **Impression Tracker** (`position_wpStory`).

Compute daily (insights/funnels, breakdown by `tag` and/or `position`, filter to the 3 story_ids):
1. **Deep-completion** — of users who fired Story Viewed at `position`=0 for a story, the % reaching its **last** `position`. Compare 4-slide days vs 3-slide days AND vs the baseline window. *The primary guardrail — does slide 4 just shed people?*
2. **Slide-4 like rate** — reuse the LR bookmark **90465031** for the added slide's news_id; is it ≥ the bucket median (i.e. the added slide actually engages)?
3. **CTA CTR** — Story CTA Click ÷ Story Viewed, overall and on the last slide.
4. **Entry rate** — unique Story Viewed users/day (trend); did more content deter *opening*?
5. **D1 return** — retention: Story Viewed (day N) → Story Viewed (day N+1). *The "not coming back" guardrail.*
6. *(bonus)* order attribution — `msp_order_placed` among story-exposed users.

**Baseline** = the 5 prior days **2026-08-23 → 2026-08-28** (all 3-slide). Read is **before/after** (no control cohort) → directional. Use only fully-baked days; D1 for the last window day won't exist by day-5 — note maturity in the DM.

## Day-5 (2026-09-02) — CONCLUSION to Slack
After the normal publish, compute experiment-window vs baseline deltas for metrics 1–5 and **`slack_send_message` a DM to `U09K92G1U1X`** containing:
- one-line verdict (expansion helped / neutral / hurt) + the deltas table (metric · baseline · experiment · Δ),
- how many of the 5 days actually went to 4 slides (supply reality),
- the **explicit ask**: *"Reply **Y** to make dynamic slide-count (4-when-quality) permanent → I'll push it live to main. Reply **N** to keep base 3+3+1."*
- caveats: before/after not A/B; metrics mature through `<asof>`; D7 not yet observable.
Keep it one message; this message is the **thread anchor** the day-6 run reads.

## Day-6 (2026-09-03) — handle the Y/N (before the normal run)
Read the operator's reply to the day-5 DM (`slack_read_thread` / search the DM):
- **Explicit Y / yes** → promote to live: edit `kc-stories-workflow.md §5` so dynamic slide-count (base 3+3+1, +1 to Mandi/FMCG only when body-verify + LR≥median) is the standing rule; remove the ACTIVE-EXPERIMENT pointer; set this file's Status → CLOSED (adopted); commit + push to main. DM a one-line "shipped ✅".
- **Explicit N / no** → keep base (already base after the window); set Status → CLOSED (rejected); commit the log; DM "reverted, keeping 3+3+1".
- **No / ambiguous reply** → do NOT change the spec. Run base pipeline, DM once more asking for Y/N, carry the decision to the next run. Treat anything not a clear affirmative as "hold."

## Rollback (any day, mid-window)
If a day's deep-completion or D1 return craters vs baseline (e.g. >20% relative drop), stop expanding immediately (revert that bucket to 3) and note it in the log + a Slack heads-up; still run the day-5 conclusion.
