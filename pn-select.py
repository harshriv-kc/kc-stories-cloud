# -*- coding: utf-8 -*-
"""
REACTIVATION PN — CONTENT SELECTOR (step 1)
===========================================
Turns a Mixpanel board report into ONE picked post, deterministically.

The routine does this:
  1. Mixpanel MCP  Get-Report(bookmark_id=<vertical>, skip_results=False)
  2. save that JSON verbatim  ->  report.json
  3. python3 pn-select.py --vertical shop_tips --report report.json

Why a script and not judgement: the ranking must be reproducible and auditable, and
the "already sent" check must never be eyeballed. Everything here is mechanical.
The only judgement left to the routine is writing the copy (step 2).

RANKING RULES (derived from the live Shop Tips report, 2026-08-17)
 * Rank by the report's `Formula` ratio, DESCENDING. That is the metric the tracker
   sheet means by "sorted in descending order".
 * Impressions FLOOR (default 5000). Necessary because ratio and reach are inversely
   related in this data: the two largest posts (111,873 / 111,571 impressions) score
   0.45 / 0.46, while the best ratios (1.62 / 1.43 / 1.19) sit at 6.4k / 8.7k / 14.4k.
   Ranking on ratio alone picks tiny-reach posts; ranking on reach alone picks weak
   ones. Floor + ratio-desc picks mid-reach, high-ratio.
 * NO text filtering happens here. The text in the report breakdown is a TRUNCATED
   preview, and so is `nc_published_posts.title` for UGC posts — both cut mid-word
   ("...sathiyoko mera na", "...is savan ke m"). The real copy source is
   `ugc_posts.post_description` (129–340 chars in the sampled window), reachable only
   by a second lookup. So this script SHORTLISTS on metrics alone and the routine
   resolves text in phase B.
 * Never re-send an item. Checked against BOTH the local ledger and the historical
   item ids already used by the live campaigns (specs/pn-corpus-duo-image.csv).

PHASE B (the routine, after this script)
  For each shortlisted id, in rank order:
      SELECT s.published_id, p.post_description
      FROM ugc_posts_stats s JOIN ugc_posts p ON p.post_id = s.post_id
      WHERE s.published_id = '<id>';
      -- editorial posts are not in ugc_posts; fall back to nc_published_posts.title
  Take the first candidate that passes the WRITABILITY TEST:
      does the description name a SUBJECT — a product, a problem, a season, a number,
      a situation — or is it only a greeting plus "watch the video"?
  It does NOT need to contain the answer. The PN withholds the method by design, so
  "how to raise sales in Sawan" is perfectly writable. What is unwritable is a post
  with no subject at all, e.g.
      "Jay hind sathiyo … is kathin samay par humko kya karna chahiye video dwara di
       gayi jankari"  -> greeting + pointer, no topic. SKIP, take the next.
  This is the one genuine judgement in the pipeline and it belongs to the routine,
  which is writing the copy anyway.
"""
import argparse, csv, json, os, re, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "pn-select-log.json")
CORPUS = os.path.join(HERE, "specs", "pn-corpus-duo-image.csv")

VERTICALS = {
    "scheme":    {"bookmark_id": 83460007, "level4_pt": "scheme"},
    "shop_tips": {"bookmark_id": 83460055, "level4_pt": "shop_tips"},
    "mandi":     {"bookmark_id": 83460168, "level4_pt": "teji_mandi"},
    "fmcg":      {"bookmark_id": 83460251, "level4_pt": "fmcg_product_change"},
}

MIN_IMPRESSIONS = 5000
SHORTLIST = 5
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def die(m):
    print(f"\n  ABORT: {m}\n"); sys.exit(1)


def parse_report(js):
    """Mixpanel insights results -> {item_id: {"text":…, metric_name: value}}.

    Shape: results[<metric>]["rows"] is a flat list of [key, value] where key is
    "<itemID>, $overall"  (value = scalar)  or  "<itemID>, <post text>"  (value = nested).
    We take the scalar from the $overall row and the text from its sibling.
    """
    res = js.get("results") or js.get("response", {}).get("results")
    if not res:
        die("no `results` in the report JSON — call Get-Report with skip_results=False")
    items = {}
    for metric, block in res.items():
        for row in block.get("rows", []):
            if not isinstance(row, list) or len(row) != 2:
                continue
            key, val = row
            if not isinstance(key, str) or ", " not in key:
                continue
            item_id, rest = key.split(", ", 1)
            if not UUID.match(item_id):
                continue
            rec = items.setdefault(item_id, {"text": None})
            if rest == "$overall":
                if isinstance(val, (int, float)):
                    rec[metric] = float(val)
            else:
                # the sibling row carries the post text; keep the longest seen
                if rec["text"] is None or len(rest) > len(rec["text"]):
                    rec["text"] = rest
    return items


def pick_metrics(items):
    """Identify which parsed metric is the ratio and which is impressions."""
    names = set()
    for r in items.values():
        names |= {k for k in r if k != "text"}
    ratio = next((n for n in names if n.strip().lower() == "formula"), None)
    imp = next((n for n in names if "impression" in n.lower()), None)
    if not ratio:
        die(f"no `Formula` metric found. Metrics present: {sorted(names)}")
    if not imp:
        die(f"no impressions metric found. Metrics present: {sorted(names)}")
    return ratio, imp


def already_used():
    used = set()
    if os.path.exists(CORPUS):
        with open(CORPUS, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("item_id"):
                    used.add(row["item_id"])
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as f:
            for r in json.load(f).get("picks", []):
                used.add(r["item_id"])
    return used


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vertical", required=True, choices=sorted(VERTICALS))
    p.add_argument("--report", required=True, help="JSON saved from Get-Report")
    p.add_argument("--min-impressions", type=int, default=MIN_IMPRESSIONS)
    p.add_argument("--shortlist", type=int, default=SHORTLIST)
    p.add_argument("--commit", metavar="ITEM_ID", default=None,
                   help="record the item the routine actually chose in phase B")
    a = p.parse_args()

    cfg = VERTICALS[a.vertical]
    with open(a.report, encoding="utf-8") as f:
        items = parse_report(json.load(f))
    if not items:
        die("parsed 0 items — is this the right report?")
    ratio_k, imp_k = pick_metrics(items)
    used = already_used()

    cands = []
    for iid, r in items.items():
        cands.append({
            "item_id": iid,
            "ratio": r.get(ratio_k),
            "impressions": r.get(imp_k),
            "title": r.get("text") or "",
        })

    def reject(c):
        if c["ratio"] is None or c["impressions"] is None:
            return "no metric"
        if c["item_id"] in used:
            return "already sent"
        if c["impressions"] < a.min_impressions:
            return f"impressions {c['impressions']:.0f} < {a.min_impressions}"
        return None

    for c in cands:
        c["reject"] = reject(c)
    eligible = sorted([c for c in cands if not c["reject"]],
                      key=lambda c: -c["ratio"])

    print("=" * 78)
    print(f"  VERTICAL : {a.vertical}  (level4_pt={cfg['level4_pt']}, report {cfg['bookmark_id']})")
    print(f"  METRICS  : ratio='{ratio_k}'  impressions='{imp_k}'")
    print(f"  FILTERS  : impressions >= {a.min_impressions} · not already sent")
    print(f"  PARSED   : {len(cands)} candidates -> {len(eligible)} eligible")
    print("=" * 78)
    print("\n  ELIGIBLE, best first:")
    for i, c in enumerate(eligible, 1):
        print(f"   {i:>2}. ratio {c['ratio']:.2f} | imp {c['impressions']:>7.0f} | {len(c['title']):>3}ch | {c['item_id']}")
        print(f"       {c['title'][:110]}")
    print("\n  REJECTED:")
    for c in sorted([c for c in cands if c["reject"]], key=lambda c: -(c["ratio"] or 0)):
        rr = f"{c['ratio']:.2f}" if c["ratio"] is not None else "  - "
        print(f"       ratio {rr} | {c['item_id'][:8]}… | {c['reject']}")

    if not eligible:
        die("nothing eligible. Widen the window in the report, or lower the floor deliberately.")

    short = eligible[:a.shortlist]
    print("\n" + "=" * 78)
    print(f"  SHORTLIST — resolve full text for these in rank order, take the first WRITABLE one")
    print("=" * 78)
    for i, c in enumerate(short, 1):
        print(f"  {i}. {c['item_id']}   ratio {c['ratio']:.2f}  imp {c['impressions']:.0f}")
    print("\n  Phase-B lookup (database=community):")
    ids = ",".join(f"'{c['item_id']}'" for c in short)
    print(f"""    SELECT s.published_id, p.post_description
    FROM ugc_posts_stats s JOIN ugc_posts p ON p.post_id = s.post_id
    WHERE s.published_id IN ({ids});""")
    print("\n  WRITABILITY TEST — does the description name a subject (product, problem,")
    print("  season, number, situation)? It need NOT contain the answer; the PN withholds")
    print("  the method by design. Reject only greeting-plus-\"watch the video\" with no topic.\n")

    if a.commit:
        chosen = next((c for c in eligible if c["item_id"] == a.commit), None)
        if not chosen:
            die(f"--commit {a.commit} is not in the eligible list; refusing to log an unranked pick.")
        log = {"picks": []}
        if os.path.exists(LEDGER):
            with open(LEDGER, encoding="utf-8") as f:
                log = json.load(f)
        if any(r["item_id"] == a.commit for r in log["picks"]):
            die(f"{a.commit} is already in the ledger — refusing to re-send.")
        log["picks"].append({"vertical": a.vertical, "item_id": chosen["item_id"],
                             "ratio": chosen["ratio"], "impressions": chosen["impressions"],
                             "rank": eligible.index(chosen) + 1,
                             "at": datetime.datetime.utcnow().isoformat() + "Z"})
        with open(LEDGER, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)
        print(f"  ledger updated -> {LEDGER}  ({chosen['item_id']}, rank {eligible.index(chosen)+1})\n")


if __name__ == "__main__":
    main()
