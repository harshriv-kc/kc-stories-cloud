# EXPERIMENT — KC Stories dynamic slide-count (Phase 1)

**Status:** ACTIVE · **Owner:** operator U09K92G1U1X (Harsh) · **Set up:** 2026-08-28
**Window (5 runs):** 2026-08-29 → 2026-09-02 · **Conclusion DM:** day-5 (2026-09-02) · **Decision handled:** day-6 (2026-09-03)
**⚑ EXTENSION (operator Harsh, 2026-09-01):** News flexes to **1–3 slides** on the last 2 days (09-02 + 09-03), 2nd/3rd from the gated UGC news pool — see **NEWS-SOURCE EXTENSION** below.

The daily routine reads this file whenever `kc-stories-workflow.md` points here. During the window it **overrides the base slide count** in workflow §5. Everything else in the pipeline is unchanged. If this file is absent or the window has passed, ignore and run the base pipeline.

---

## Hypothesis
Adding a 4th slide to Mandi and/or FMCG **when a genuinely high-quality 4th post exists** grows content consumption **without** hurting entry, completion, or next-day return. If it hurts any of those, revert to base.

## What changes during the window (the ONLY change)
- **Mandi** and **FMCG** may publish **4 slides** instead of 3 — but a 4th is added **only if** it passes §6 body-verify (concrete ₹ number) **AND** its LR ≥ that bucket's trailing-7-day median LR. Otherwise stay at 3. **Never pad with a weak/no-number 4th** (SKIP-ALWAYS still binds).
- **News now flexes to 1–3** (operator Harsh, 2026-09-01 — folded into the last 2 window days 09-02 + 09-03). Slide 1 stays the best in-house Trending News. Slides 2–3 come from the **UGC news pool** and are added only when they clear the hard gates in **NEWS-SOURCE EXTENSION** below. If nothing qualifies, News falls back to 1 — never pad.
- So a day can be 3+3+1 (nothing extra qualifies) or up to 4+4+3. The log records which and why.
- All dedup (news_id 12d + brand 7d), QC, badge, PN, and ledger steps are **unchanged**. PN stays the fixed 3 icons (mandi/fmcg/tn — the extra news slides live inside the Trending News reel only, never a 4th PN icon).

## ⚑ NEWS-SOURCE EXTENSION — UGC news, 2nd/3rd slide (operator Harsh, 2026-09-01)
**Why:** the LR bookmark's `news` pool is 100% in-house; UGC news (retailer-written किराना समाचार / market-event posts) is not in the bookmark, so it has **no Like-Rate signal**. Verified 2026-09-01 that UGC still carries 3–4 genuine news items/day — but a naive frequency scan is contaminated by (a) copy-paste **template/example** text (e.g. the evergreen `"उदाहरण - भारत सरकार ने सोया तेल के निर्यात पर 10% टैक्स…"` reposted for 5+ months) and (b) **unsourced rumor bait** (e.g. `"10 मिनट डिलीवरी बंद"`, `"11.5 लाख दुकानें बंद"`). These gates keep those out.

**Engagement proxy (no LR available):** distinct-user repost frequency over the last ~48h — `COUNT(DISTINCT user_id)` on the deduped body. Higher = more retailers independently posted it.

**Pick rule — News = best-1 in-house + up to 2 UGC, each UGC slide MUST clear ALL of:**
1. **Real target:** `ugc_posts_stats.published_id` is a genuine UUID (NOT the literal `"ugc"` placeholder) — else it has no redirect and can't be a slide.
2. **Fresh, not a template:** the identical body text must NOT have appeared >72h ago (query the same normalized text across a wider window; if its earliest copy is older than 72h it's an evergreen template/example → reject). Also literally reject any body starting with `उदाहरण`/`Example`.
3. **Concrete + verifiable:** a concrete number or a concrete market/supply/price event (a mandi/commodity move with a figure, a weather/crop-supply shock, a real MRP/GST change with the old→new price). **Reject unsourced sensational policy/ban claims** that carry no number and can't be corroborated by an in-house post — those are the rumor trap.
4. **Non-bait, non-digest:** SKIP scam/fraud/arrest bait AND रुझान/mandi-price-digest posts (those belong in the Mandi reel, not News).
5. **Distinct topic** from slide 1 and from each other (no two milk-price slides).
6. **Dedup-clean:** `news_id` not in the 12-day ledger set; add each published UGC news `news_id` to the ledger like any other pick.
7. **Ranked** by the distinct-user proxy desc; take the top 1–2 that clear 1–6. If fewer qualify, publish fewer (1 is fine). Body-verify each before generating its card, same as §6.

Card = the normal news template (black stripe, `.news` summary). Badge/PN unchanged (still 3 icons; the tn badge represents the reel's lead news).

**Scan (starting point — all UGC, no tag filter, deduped by body, freshness-checked):**
```sql
SELECT s.published_id, p.post_description, COUNT(DISTINCT p.user_id) users,
       MIN(p.created_at) first_seen
FROM ugc_posts p JOIN ugc_posts_stats s ON s.post_id=p.post_id
WHERE p.created_at >= UNIX_TIMESTAMP(NOW() - INTERVAL 2 DAY)*1000 AND p.is_active=1
  AND s.published_id <> 'ugc'
  AND p.post_description NOT LIKE 'उदाहरण%'
  AND p.post_description REGEXP '<news signals: सरकार|योजना|जीएसटी|GST|सिलेंडर|बारिश|बाढ़|आयात|निर्यात|मंडी|तेजी|मंदी|महंगा|सस्ता|प्रतिबंध|अलर्ट …>'
GROUP BY s.published_id
HAVING users >= 2 AND first_seen >= UNIX_TIMESTAMP(NOW() - INTERVAL 72 HOUR)*1000
ORDER BY users DESC LIMIT 40;
```
Then apply gates 1–7 by eye + a §6 body-verify. (This is an interim proxy. The durable fix is the Phase-2 enable-gate: widen bookmark 90465031 to expose UGC-news LR so these reuse the real LR + median machinery.)

## Per-day logging (every run in the window)
After publishing, append one object to `experiment-slide-count-log.json → days[]`:
```
{ "date": "YYYY-MM-DD",
  "mandi_slides": 3|4, "fmcg_slides": 3|4, "news_slides": 1|2|3,
  "mandi_4th": {"news_id","brand","LR","bucket_median_LR"} | null,
  "fmcg_4th":  {"news_id","brand","LR","bucket_median_LR"} | null,
  "news_ugc_extra": [ {"news_id","topic","users_proxy","first_seen","why"} ] | [],   // the UGC 2nd/3rd slides added (empty if none qualified)
  "reason": "why 3 or 4 per bucket (LR vs median), and why N news (which UGC items cleared/failed the gates)",
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
- **NEWS-SOURCE EXTENSION (added 09-01, ran 09-02 + 09-03):** also report how many UGC news slides went live, which items cleared the gates vs were rejected (templates/rumors), and their per-slide completion + CTA CTR vs the in-house lead news slide. Add a second Y/N line: *"Reply **NEWS-Y** to keep 2–3 news (UGC-sourced, gated) → I'll wire it into §5 + file the Phase-2 bookmark-widen so it gets a real LR signal. **NEWS-N** to revert to News=1."* (Only 2 days of news data, so flag it as thinner/directional.)
- caveats: before/after not A/B; metrics mature through `<asof>`; D7 not yet observable; the UGC-news proxy is repost-frequency, not LR — the durable fix is widening bookmark 90465031.
Keep it one message; this message is the **thread anchor** the day-6 run reads.

## Day-6 (2026-09-03) — handle the Y/N (before the normal run)
Read the operator's reply to the day-5 DM (`slack_read_thread` / search the DM):
- **Explicit Y / yes** → promote to live: edit `kc-stories-workflow.md §5` so dynamic slide-count (base 3+3+1, +1 to Mandi/FMCG only when body-verify + LR≥median) is the standing rule; remove the ACTIVE-EXPERIMENT pointer; set this file's Status → CLOSED (adopted); commit + push to main. DM a one-line "shipped ✅".
- **Explicit N / no** → keep base (already base after the window); set Status → CLOSED (rejected); commit the log; DM "reverted, keeping 3+3+1".
- **No / ambiguous reply** → do NOT change the spec. Run base pipeline, DM once more asking for Y/N, carry the decision to the next run. Treat anything not a clear affirmative as "hold."
- **NEWS-Y** → promote the news-source rule: add the UGC 2nd/3rd-news gates (this file's NEWS-SOURCE EXTENSION) into `kc-stories-workflow.md §5` News as the standing rule, and file the Phase-2 ticket to widen bookmark 90465031 (so the proxy is replaced by real LR). **NEWS-N** → revert to News=1. Handle independently of the slide-count Y/N (they're separate decisions in the same DM).

## Rollback (any day, mid-window)
If a day's deep-completion or D1 return craters vs baseline (e.g. >20% relative drop), stop expanding immediately (revert that bucket to 3) and note it in the log + a Slack heads-up; still run the day-5 conclusion.
