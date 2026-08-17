# Reactivation PN automation — 4 daily image PNs, zero human intervention

**Source of the brief:** "Reactivation Tracker" sheet (4 rows: Scheme 06:30, Shop Tips 08:30, Mandi 13:30,
FMCG — time blank) + 4 Mixpanel short links.
**Goal:** a routine that picks content, writes copy, generates images and schedules all 4 PNs daily,
unattended.
**Status:** selection mechanic RESOLVED. Copy rules NOT resolved (no machine-readable record exists —
see §5). Feasibility quantified in §3; Shop Tips is the one hard blocker.

---

## 1. What the 4 PNs actually are

All four are the **same PN**: one `duo_image` custom-render push, one item, once a day. They differ in
exactly three things — the content bucket, the send time, and the copy voice.

The bucket is the Mixpanel/DB field `level4_pt`, set at moderation time by the UGC moderator LLM
(`UGCPostModerator/.../prompts/sections.py:280`) or on editorial upload
(`d2r-dashboard-BE/backend/logic/newsUpload.js:243`).

| Sheet row | Time IST | `level4_pt` | Sheet's selection note |
|---|---|---|---|
| Scheme | 06:30 | `scheme` | "apply item ID - level 4 filter as scheme" |
| Shop Tips | 08:30 | `shop_tips` | "apply item ID - level 4 filter as Shop tips" |
| Mandi | 13:30 | `teji_mandi` | "level 4 filter as teji Mandi; if no mandi post, pick from in-app posts" |
| FMCG | *blank* | `fmcg_product_change` | "sorted descending, choose by headline — does it give value, can a clickbaity PN be written on it" |

Full `level4_pt` vocabulary (so nothing is guessed): `rate_and_margin`, `product_review`, `scheme`,
`shop_tips`, `teji_mandi`, `news`, `new_product_launch`, `fmcg_product_change`, `entertainment`,
`reward_and_thank_you`, `wish_post`, `super_order`.

**So the selection logic is one query with one variable.** Not four different systems. That is the
finding that makes this automatable.

## 2. Where the ranking comes from

Two independent, already-in-production paths. Both are usable; they answer different questions.

### 2a. Mixpanel saved report (what the team does today)
`level4_pt` is a column of the **posts lookup table** pushed to Mixpanel by
`CRONS/news_metrics_updater_gen2` (`LOOKUP_TABLE_ATTRIBUTES` includes `level4_pt`;
`LOOKUP_TABLE_IDS = [48ace223-…, 7369ce03-…]`). That is why the sheet says "item ID - level 4 filter":
in the UI you break down by the `itemID` dimension and filter on its `level4_pt` column.

A saved report can be read programmatically — proven in prod:

```python
# CRONS/news_metrics_updater_gen2/get_top_ugcs.py
f"https://mixpanel.com/api/2.0/insights?project_id=2551336&bookmark_id={bookmark_id}"
auth=(SERVICE_ACCOUNT_TOKEN, PROJECT_TOKEN)
```

Per-vertical report IDs already wired up elsewhere (`FLEET_ADS/fleetV2Hourly/constants.py`):

| vertical | bookmark_id |
|---|---|
| `fmcg_product_change` | 87788037 |
| `rate_and_margin` | 87788156 |
| `government_schemes` | 87788218 |
| `yt_videos` | 87788227 |
| `shop_tips` | 87788238 |
| `teji_mandi` | 87788252 |
| `scheme` | 87788262 |
| FMCG CTR-based | 88924344 |
| Top CTR news (high-impression) | 88985386 |

⚠️ These are the **D0 feed experiment** reports, not provably the 4 the sheet links to. The sheet's
`mixpanel.com/s/…` short links are auth-gated and cannot be resolved to bookmark IDs from here (302 →
`/request_access/`). Getting the 4 real IDs is ask #1 in §6.

### 2b. SQL (better for an unattended routine)
`main.post_categories` carries an indexed `level4_pt` column plus `visible_from`, and joins to
`main.post_interactions` for impressions/likes/shares/comments:

```sql
SELECT pc.post_id, pi.no_of_impressions, pi.no_of_likes
FROM post_categories pc
JOIN post_interactions pi ON pi.post_id = pc.post_id
WHERE pc.level4_pt = '<vertical>'
  AND pc.visible_from >= (UNIX_TIMESTAMP() - <staleness_days>*86400)*1000
  AND pi.no_of_impressions >= 1000
ORDER BY pi.no_of_likes / pi.no_of_impressions DESC;
```

`post_interactions` has **no clicks column**, so true CTR is Mixpanel-only. SQL gives a like/comment/share
ranking; Mixpanel gives CTR. Production's own scorer weights likes highest anyway
(`get_top_ugcs.py`: `0.2*click + 0.6*like + 0.2*comment`, impression floor 500, top-10 floor 1000), so
the SQL proxy is close to the real thing and has no auth dependency.

### Freshness, per vertical (production rule, `FLEET_ADS/fleetV2Hourly/get_data.py:122-138`)
- `teji_mandi`, `wish_post` → drop older than **3 days**
- `scheme`, `shop_tips`, `fmcg_product_change` → drop older than **15 days**
- `rate_and_margin`, `reward_and_thank_you` → drop older than **30 days**

That matches the sheet's own instinct — mandi is perishable, shop tips are evergreen.

## 3. Feasibility — measured 2026-08-17, 15-day window

| vertical | posts in window | ≥500 imp | ≥1000 imp | avg imp | eligible/day | verdict |
|---|---|---|---|---|---|---|
| `scheme` | 2,500 | 635 | 451 | 680 | ~30 | ✅ safe |
| `teji_mandi` | 1,174 | 289 | 190 | 1,838 | ~13 | ✅ safe (3d window → 246 raw) |
| `fmcg_product_change` | 1,472 | 48 | 24 | 232 | ~1.6 | ⚠️ tight |
| `shop_tips` | **57** | 15 | **11** | 9,768 | **~0.7** | ❌ cannot sustain daily |

Read the two outliers, they explain the whole risk profile:

- **`shop_tips` is supply-starved** — ~4 posts/day created, 11 in 15 days clear 1,000 impressions. A
  daily 08:30 PN burns more than the platform produces. Production already works around this: FLEET
  keeps a **30–120 day shop_tips backfill pool** that bypasses staleness filtering
  (`get_data.py:331-337`). The routine must do the same, and must dedupe against everything already
  sent or it will re-push the same tip inside a week.
- **`fmcg_product_change` is distribution-starved** — lots of posts (98/day), almost no impressions
  (avg 232). Ranking on impressions barely discriminates. This is why the team's FMCG note is the only
  one that says "read the headline and judge" rather than "take the top row" — and why there is a
  separate CTR-based FMCG report (88924344). Either drop the floor to ~200 or rank on CTR.

## 4. Scheduling — already built

Nothing new is needed on the WebEngage side. `pn-schedule.py` + `specs/pn-campaign-registry.json`
already schedule `duo_image` PNs through the d2r pipeline, and as of the default-audience change any
new duo_image type inherits the house reactivation audience (include AND `~14c4aac` + `~8172j8k`,
exclude OR `~725k98n` + `h249a16`) without restating it. Four new registry entries — or one plus
`--new-duo-image` — cover all four sends.

Feedback loop for later: `main.webengage_campaign_analytics.ctr` is campaign-level CTR, so the routine
can be told which verticals and copy styles actually earn their slot.

## 5. Copy — SOLVED, scraped from history

`community.webengage_notification_history` holds **16,326 rows**, every one with `entity_id` plus
`titles`/`messages` as rich HTML. The copy was never lost, only wrapped in markup. Per-vertical
campaigns exist and were scraped:

| vertical | campaigns in history | sends |
|---|---|---|
| Scheme | `Scheme Post 1`, `Scheme post 2`, `government schemes` | ~549 |
| Mandi | `Teji Mandi Report ` | 138 |
| Shop Tips | `Trending News Shop Tips` + 3 `Reactivation Exp` rows | ~37 |
| FMCG | `Trending News Fmcg` | 25 |

**The copy is slot-filling, not freehand creative.** Each vertical has a fixed 2–3 line skeleton, a
small rotating pool of intensifiers/emoji/verbs, and one or two slots that depend on the post. Mandi's
second line is a byte-identical constant across all 7 sampled sends. Full templates, shipped examples
and the per-vertical devices are in **`specs/pn-copy-playbook.md`**.

The 3-line skeleton maps 1:1 onto the image kit's slots (line 1 → `--head`, line 2 → `--sub`, line 3 →
the CTA button the kit already draws), so no translation layer is needed and the CTA never has to be
written.

The 3 `Reactivation Exp` rows also turned out to be `template_type: dismiss`, `screen: KiranaLive` —
**not** `duo_image`. Their distinguishing moves (a personalisation token with Hindi fallback, and the
outcome reframed as a distress question) are documented in the playbook. Note the Jinja token cannot
survive into a `duo_image` image — pixels are rendered before WebEngage sees them.

## 6. What is needed to finish this

1. **FMCG send time** (blank in the sheet).
2. **Campaign identity** — one WebEngage campaign reused for all 4 verticals, or 4 separate ones? The
   sheet says 13:30 = Mandi; the existing registry entry `reactivation_exp_image_pn` is 13:30 and
   named "Reactivation Exp (Image PN, Shop Tips)". Those cannot both be right, and the answer decides
   whether the registry gets 1 entry or 4.
3. **Shop Tips policy call** — with ~0.7 eligible posts/day, pick one: (a) draw from the 30–120 day
   backfill pool with a no-repeat ledger, (b) drop 08:30 to 2–3×/week, or (c) let it fall back to
   another vertical when the pool is dry.
4. *(optional)* **The 4 Mixpanel bookmark IDs** behind the short links `1dPtGm` / `2304fn` / `p0Exu` /
   `1uJpzH` — only needed if you want CTR-based ranking rather than the SQL engagement ranking in §2b.
   The links are auth-gated (302 → `/request_access/`), so they have to come from your browser.

## 7. Shape of the routine (once §6 is answered)

Per vertical, once a day, at its own time:

1. **Select** — rank the bucket (SQL or bookmark), apply the vertical's staleness window and impression
   floor, drop anything in `webengage_notification_history` or the local sent-ledger, take the top row.
2. **Resolve** — item title/description/media from `nc_published_posts` / `ugc_posts` (already in the PN
   image kit, Part 2). Media is **reference only** — never shipped as the PN image.
3. **Write** — headline + optional subline in the vertical's voice (blocked on §6.2).
4. **Render** — the kit's engine: 4:3 expanded, 3:1 collapsed, AI background, photorealistic.
5. **Schedule** — `pn-schedule.py --type <vertical> --entity <itemID> --nd … --time …`, inheriting the
   default reactivation audience.
6. **Log** — append to the sent-ledger so tomorrow cannot repeat today.

Steps 1, 2, 4, 5, 6 are all solved or trivially solvable now. Step 3 is the only one waiting on input.
