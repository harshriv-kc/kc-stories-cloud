# Reactivation PN automation — master architecture

**End goal:** for each of the 7 daily send slots, a routine sources one post from the right Mixpanel
report, writes copy in that vertical's voice, generates + renders the two images, schedules the PN, and
records the item — with no human in the loop. This doc is the map; the moving parts are listed under
each stage.

This supersedes the piecemeal notes in `reactivation-pn-automation.md` and `pn-copy-playbook.md`
(both still valid as background). The two things that changed the design after looking at the *live*
reports: the four reports are not the same shape, and their reach numbers are not on the same scale.

## The one idea that shapes everything

**The four verticals are four different data sources wearing the same output.** The output is identical —
one `duo_image` PN, 4:3 + 3:1, scheduled into a slot. But the *input* — which report, how it ranks, how
its post text is structured, what the copy deletes — differs per vertical. So the system is:
**generic engine + per-vertical config.** All the difference lives in `specs/pn-verticals.json`; the
code (`pn-select.py`) knows nothing vertical-specific.

## The pipeline (what runs, per slot, per day)

```
 1. SOURCE   Mixpanel Get-Report(report_id)  ──►  pn-select.py  ──►  ranked shortlist
 2. RESOLVE  ugc_posts.post_description for the shortlist  ──►  writability test  ──►  1 post
 3. WRITE    vertical copy template + psyche  ──►  headline + subline
 4. IMAGE    generate_story_image ×2 (expanded scene, collapsed detail)  [AI, no restrictions]
 5. RENDER   kc-pn-kit engine.py  ──►  1000×750 + 1000×333 webp
 6. APPROVE  show the preview; copy AND art are AI, both need a human yes
 7. SCHEDULE pn-schedule.py --type <campaign_key> --entity <itemID> --nd …  ──►  WebEngage slot
 8. LOG      append itemID to pn-select-log.json  (never repeats)
```

Stages 1–2, 5, 7–8 are mechanical and built. Stage 3 is templated. Stage 4 is generation. Stage 6 is
the only gate, and it's the one place a human is still required (by design, until you trust it).

## Stage 1 — SOURCE: the config-driven ranker

`pn-select.py` is generic. It reads `pn-verticals.json`, then for the named vertical:

1. Parse the report → `{itemID: metrics + reach + text-preview}`.
2. **Rank** by the vertical's `rank_metrics` under its `rank_mode`:
   - `primary` — rank by metric[0], break ties with the rest (Shop Tips, Scheme, Mandi).
   - `sum` — add the metrics (FMCG: `Like% + Comment%`, because it has no single Formula).
3. **Reach gate — relative, never absolute.** Keep posts at/above the *median reach of their own
   report*. This is the pivotal fix: the impression column is a per-interaction average whose scale
   differs 25× across reports, so a flat 5,000 floor deleted all 68 Scheme posts while keeping 73
   Mandi ones. Median-relative self-calibrates (Scheme gate ≈ 820, Mandi ≈ 3,100).
4. **Dedupe** against the ledger + the 115 item IDs already used by live campaigns.
5. Emit the top-5 shortlist.

Proven on all four live reports (2026-08-19):

| vertical | report | rank metric | posts | eligible after gate+dedupe |
|---|---|---|---|---|
| shop_tips | 83460055 | Formula | 18 | 13 |
| scheme | 83460007 | Formula (+F2) | 68 | **34** (was 0 under a 5k floor) |
| mandi | 83460168 | Formula (+F2) | 220 | 110 |
| fmcg | 83460251 | Like%+Comment% | 32 | 12 |

## Stage 2 — RESOLVE + the writability test

The report's post text is a *truncated preview* (cuts mid-word for UGC). The real copy source is
`ugc_posts.post_description` (join via `ugc_posts_stats.published_id`); editorial posts fall back to
`nc_published_posts.title`. For each shortlisted post in rank order, take the first that passes the
**writability test**: does it name a subject to delete? Reject "namaskar … watch the video" with no
topic. This is the single human-ish judgement, and it belongs to whoever writes the copy anyway.

Optional **specificity tiebreak** (within the top 3 only): a post with a number, a named rival, a
brand, or a festival beats a bland one of similar rank; ties fall back to the metric; the override can
never reach past position 3.

## Stage 3 — WRITE: same move, per-vertical target

Every vertical uses the one move — **state the subject, delete the answer, point at it** — but the
report tells you which field is the answer to delete:

| vertical | source shape | delete | example |
|---|---|---|---|
| scheme | `<Product> - <offer>` | the free item / quantity | *KitKat, 1 jaar → 2 units free* ⇒ "किटकैट पर ज़बरदस्त स्कीम / क्या मुफ़्त मिल रहा है?" |
| mandi | `कमोडिटी: X / तेजी या मंदी: ↑` | the direction + ₹ | *नारियल, तेज़ी* ⇒ "नारियल के भाव में बदलाव / अभी नया रेट देखें" |
| fmcg | `प्रोडक्ट: X / बदलाव: रेट` | the new rate/weight | *टाटा नमक ₹32, रेट* ⇒ "टाटा नमक का नया रेट / देखें कितना बदला" |
| shop_tips | free-form | the method | *Sawan sales* ⇒ "इस सावन बढ़ेगी दुकान की सेल / बस अपनाएं ये तरीका" |

Then the shared grammar: quote the load-bearing words, 2 lines (add a subline only if there's a second
beat), CTA is the kit's button (never written), colour = temperament (offer→yellow, alert→red,
profit→green, news→black). Allowed, per your calls: adding a stake not in the post; any brand/product
in the image. Full detail in `pn-copy-playbook.md` / `pn-image-writing-psychology.md`.

## Stages 4–8 — already built

Image via `generate_story_image` (MCP timeout now 5 min, was 60s). Render via the kit (`band` layout
reads best for the presenter-forward look; generate the scene with headroom above the subject so the
crop never clips the face). Schedule via `pn-schedule.py` into the slot's `campaign_key`, inheriting
the default reactivation audience. Log to `pn-select-log.json`.

## Supply vs demand — the real constraint

7 slots/day is the demand. Supply, measured against the live reports:

- **Mandi — abundant** (220 posts, 110 eligible). Can carry several slots a day.
- **Scheme — abundant in count** (68 posts, 34 eligible), though every pick is low-reach by nature.
- **FMCG — moderate** (32 posts, 12 eligible).
- **Shop Tips — the bottleneck** (~1 fresh usable post/day). **It cannot fill a daily slot**, let
  alone the two the default slot map gives it. It needs a 30–120 day backfill pool (FLEET already keeps
  one) with a no-repeat ledger, or a reduced cadence.

So the routine is safe on Mandi/Scheme/FMCG and constrained on Shop Tips — plan the slot map around that.

## What's built vs what's still a decision

**Built & tested:** the config (`pn-verticals.json`), the generic ranker (`pn-select.py`, all 4
report shapes), the kit render, `pn-schedule.py`, the ledger, the copy psyche.

**Decisions before it runs unattended** (tracked in `pn-verticals.json._open_decisions`):
1. **Slot → vertical map** — two slots are `null`; Shop Tips is over-assigned vs its supply.
2. **Scheme/Mandi rank metric** — defaulted to `Formula` primary, `Formula 2` tiebreak. Confirm
   Formula is the intended one (I don't know what Formula 2 measures).
3. **FMCG rank metric** — defaulted to `Like% + Comment%` sum since it has no Formula. Confirm.
4. **Registry entries** — only `shop_tips` (`reactivation_exp_image_pn`) exists in
   `pn-campaign-registry.json`. Scheme, Mandi, FMCG each need one (audience + kvPairs) before
   `pn-schedule.py` can send them.
5. **Approval** — stage 6 is currently a hard human gate. Removing it is the last step to
   "no intervention," and should come only after a batch of supervised sends looks right.
