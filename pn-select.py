# -*- coding: utf-8 -*-
"""
REACTIVATION PN — CONTENT SELECTOR  (config-driven, all four verticals)
======================================================================
One generic ranker. Every vertical-specific rule lives in specs/pn-verticals.json,
because the four board reports are NOT the same shape:

  vertical    ranking metric(s)              reach scale (avg impressions)
  ---------   ----------------------------   -----------------------------
  shop_tips   Formula                        500 - 131k
  scheme      Formula, Formula 2             502 -   4.5k   <- 25x smaller
  mandi       Formula, Formula 2             502 - 116k
  fmcg        Like% + Comment%  (no Formula) 1k  -  44k

Two consequences baked in here:

 * NO ABSOLUTE IMPRESSION FLOOR. Reach is gated RELATIVE to each report (default:
   at/above that report's median). A flat 5,000 floor deletes all 68 Scheme posts
   while keeping 73 Mandi ones - reach is not comparable across reports.
 * RANKING METRIC IS PER VERTICAL. 'primary' ranks by the first metric, ties broken
   by the rest. 'sum' adds them (FMCG has no single Formula).

FLOW
  1. Mixpanel MCP  Get-Report(report_id, skip_results=False)  ->  report.json
       (large reports save to a file automatically; pass that path)
  2. python3 pn-select.py --vertical <name> --report report.json
       -> ranks, dedupes, prints a shortlist + the phase-B lookup SQL
  3. routine resolves post_description for the shortlist, applies the writability
     test, and (optionally) --descriptions <json> for the specificity tiebreak
  4. python3 pn-select.py ... --commit <item_id>   (records the actual pick)

The only judgement in the loop is the writability skip in phase B; everything else
is mechanical and reproducible.
"""
import argparse, csv, json, os, re, sys, datetime, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "specs", "pn-verticals.json")
LEDGER = os.path.join(HERE, "pn-select-log.json")
CORPUS = os.path.join(HERE, "specs", "pn-corpus-duo-image.csv")

SHORTLIST = 5
TIEBREAK_BAND = 3
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def die(m):
    print(f"\n  ABORT: {m}\n"); sys.exit(1)


# ---------------------------------------------------------------- config
def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- report parse
def parse_report(js):
    """Mixpanel insights results -> {item_id: {"text":…, <metric>: float, …}}.

    Each metric block has rows [key, value]; key is '<itemID>, $overall' (scalar) or
    '<itemID>, <post text>' (nested). We take the scalar and, from the sibling, the
    longest post-text preview seen (still truncated - real text comes in phase B).
    """
    res = js.get("results") or js.get("response", {}).get("results")
    if not res:
        die("no `results` in the report JSON - call Get-Report with skip_results=False")
    items = {}
    for metric, block in res.items():
        for row in block.get("rows", []):
            if not isinstance(row, list) or len(row) != 2:
                continue
            key, val = row
            if not isinstance(key, str) or ", " not in key:
                continue
            iid, rest = key.split(", ", 1)
            if not UUID.match(iid):
                continue
            r = items.setdefault(iid, {"text": None})
            if rest == "$overall":
                if isinstance(val, (int, float)):
                    r[metric] = float(val)
            elif r["text"] is None or len(rest) > len(r["text"]):
                r["text"] = rest
    return items, list(res.keys())


def impressions_key(metric_names):
    return next((m for m in metric_names if "impression" in m.lower()), None)


def resolve_metrics(cfg_metrics, present, vname):
    """Map config metric names to the actual keys present, tolerating minor casing."""
    resolved = []
    low = {m.lower(): m for m in present}
    for want in cfg_metrics:
        if want in present:
            resolved.append(want)
        elif want.lower() in low:
            resolved.append(low[want.lower()])
        else:
            die(f"vertical '{vname}' expects metric '{want}' but the report only has: {present}")
    return resolved


def score(item, metrics, mode):
    vals = [item.get(m) for m in metrics]
    if any(v is None for v in vals):
        return None
    if mode == "sum":
        return (sum(vals),)
    return tuple(vals)  # primary: metrics[0], then tiebreaks, compared left-to-right


# ---------------------------------------------------------------- dedupe
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


# ---------------------------------------------------------------- specificity (phase B)
SIG_NUM = re.compile(r"[0-9०-९]|₹|%|रुपए|रुपये|किलो|ग्राम|लीटर|पैकेट|पीस|पेटी|दर्जन")
SIG_RIVAL = re.compile(r"सुपर\s?मार्केट|सुपरमार्केट|मॉल|ऑनलाइन|बड़ी दुकान|होलसेल|थोक|"
                       r"कंपनी|कंपनियां|कंपनियों|ब्लिंकिट|जेप्टो|क्विक|डी\s?मार्ट|रिलायंस")
SIG_SEASON = re.compile(r"सावन|त्योहार|त्यौहार|दिवाली|दीवाली|राखी|रक्षाबंधन|होली|ईद|"
                        r"नवरात्र|तीज|पंचमी|15 अगस्त|१५ अगस्त|गणेश|दशहरा|नवरात्रि|करवा")
BRANDS_DEVANAGARI = [
    "कैडबरी", "पतंजलि", "डाबर", "कोलगेट", "मैगी", "सर्फ", "निविया", "फेना", "घड़ी",
    "निरमा", "अमूल", "पारले", "ब्रिटानिया", "टाटा", "हल्दीराम", "लक्स", "लाइफबॉय",
    "बिसलेरी", "कैम्पा", "थम्सअप", "हॉर्लिक्स", "बोर्नविटा", "वीम", "रिन", "एरियल",
    "टाइड", "संतूर", "डेटॉल", "सेवलॉन", "नाइसिल", "बोरोलीन", "विक्स", "ईनो",
    "हिमालय", "इमामी", "गोदरेज", "नेस्ले", "आईटीसी", "बिंगो", "किटकैट", "डेयरी मिल्क",
    "किटकैट", "कुरकुरे", "फॉर्च्यून",
]


def specificity(desc):
    hits, s = [], 0
    if SIG_NUM.search(desc): s += 2; hits.append("number")
    if SIG_RIVAL.search(desc): s += 2; hits.append("rival")
    b = next((x for x in BRANDS_DEVANAGARI if x in desc), None)
    if b: s += 2; hits.append(f"brand:{b}")
    if SIG_SEASON.search(desc): s += 1; hits.append("occasion")
    if len(desc) >= 150: s += 1; hits.append("long")
    return s, hits


# ---------------------------------------------------------------- ledger write
def commit_pick(vname, chosen, rank):
    log = {"picks": []}
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as f:
            log = json.load(f)
    if any(r["item_id"] == chosen["item_id"] for r in log["picks"]):
        die(f"{chosen['item_id']} is already in the ledger - refusing to re-send.")
    log["picks"].append({"vertical": vname, "item_id": chosen["item_id"], "rank": rank,
                         "at": datetime.datetime.utcnow().isoformat() + "Z"})
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"  ledger updated -> {LEDGER}  ({chosen['item_id']}, rank {rank})\n")


# ---------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vertical", required=True)
    p.add_argument("--report", required=True, help="JSON saved from Get-Report")
    p.add_argument("--shortlist", type=int, default=SHORTLIST)
    p.add_argument("--descriptions", default=None, help="phase B: JSON {item_id: post_description}")
    p.add_argument("--skip", default="", help="phase B: comma-separated ids judged unwritable")
    p.add_argument("--commit", default=None, metavar="ITEM_ID", help="record the phase-B pick")
    a = p.parse_args()

    cfg = load_config()
    if a.vertical not in cfg["verticals"]:
        die(f"unknown vertical. Configured: {', '.join(cfg['verticals'])}")
    vc = cfg["verticals"][a.vertical]

    with open(a.report, encoding="utf-8") as f:
        items, metric_names = parse_report(json.load(f))
    if not items:
        die("parsed 0 items - is this the right report?")

    imp_k = impressions_key(metric_names)
    if not imp_k:
        die(f"no impressions metric in report. Present: {metric_names}")
    rank_metrics = resolve_metrics(vc["rank_metrics"], metric_names, a.vertical)
    mode = vc.get("rank_mode", "primary")

    # relative reach floor
    imps = [r.get(imp_k) for r in items.values() if r.get(imp_k) is not None]
    rf = vc.get("reach_floor", "median")
    if isinstance(rf, (int, float)):
        floor = float(rf); floor_desc = f"absolute {int(floor)}"
    else:
        floor = statistics.median(imps) if imps else 0
        floor_desc = f"median of this report ({int(floor)})"

    used = already_used()
    cands = []
    for iid, r in items.items():
        sc = score(r, rank_metrics, mode)
        cands.append({"item_id": iid, "score": sc, "reach": r.get(imp_k),
                      "text": r.get("text") or "",
                      "metrics": {m: r.get(m) for m in rank_metrics}})

    def reject(c):
        if c["score"] is None: return "missing ranking metric"
        if c["reach"] is None: return "no reach value"
        if c["item_id"] in used: return "already sent"
        if c["reach"] < floor: return f"reach {int(c['reach'])} < floor"
        return None

    for c in cands: c["reject"] = reject(c)
    eligible = sorted([c for c in cands if not c["reject"]], key=lambda c: c["score"], reverse=True)

    print("=" * 80)
    print(f"  VERTICAL  : {a.vertical}  (level4_pt={vc['level4_pt']}, report {vc['report_id']})")
    print(f"  RANK BY   : {rank_metrics}  mode={mode}")
    print(f"  REACH GATE: {floor_desc}   [scale-relative, not absolute]")
    print(f"  PARSED    : {len(cands)} posts -> {len(eligible)} eligible after gate+dedupe")
    print("=" * 80)
    for i, c in enumerate(eligible[:a.shortlist], 1):
        ms = "  ".join(f"{m}={c['metrics'][m]:.2f}" for m in rank_metrics)
        print(f"  {i}. {c['item_id']}  {ms}  reach={int(c['reach'])}")
        print(f"     {c['text'][:100]}")
    if not eligible:
        die("nothing eligible. Report may be stale/empty, or every top post already sent.")

    # ------- phase A only (no descriptions): print the lookup and stop
    if not a.descriptions:
        short = eligible[:a.shortlist]
        ids = ",".join(f"'{c['item_id']}'" for c in short)
        print("\n  PHASE B - resolve full text for the shortlist (database=community):")
        print(f"""    SELECT s.published_id, p.post_description
    FROM ugc_posts_stats s JOIN ugc_posts p ON p.post_id = s.post_id
    WHERE s.published_id IN ({ids});
    -- editorial posts absent from ugc_posts: fall back to nc_published_posts.title""")
        print(f"\n  WRITABILITY TEST ({vc['text_shape']}): does it name a subject to delete")
        print(f"  ({vc['delete_target']})? Reject greeting + 'watch the video' with no subject.")
        print("\n  (re-run with --descriptions <json> [--skip ids] to apply the specificity tiebreak)\n")
        return

    # ------- phase B: specificity tiebreak within the writable top band
    descs = json.load(open(a.descriptions, encoding="utf-8"))
    skip = {x.strip() for x in a.skip.split(",") if x.strip()}
    band = [c for c in eligible if c["item_id"] in descs and c["item_id"] not in skip][:a.shortlist]
    if not band:
        die("every shortlisted post was skipped/unwritable - widen --shortlist")
    band3 = band[:TIEBREAK_BAND]
    for c in band3:
        c["desc"] = descs[c["item_id"]]
        c["spec"], c["sigs"] = specificity(c["desc"])
    print("=" * 80)
    print(f"  PHASE B - specificity tiebreak within top {len(band3)} writable")
    print("=" * 80)
    for i, c in enumerate(band3, 1):
        print(f"  {i}. {c['item_id']}  score={c['score']}  spec={c['spec']} [{', '.join(c['sigs']) or 'none'}]")
        print(f"     {c['desc'][:150]}")
    if skip:
        print(f"\n  skipped unwritable: {', '.join(sorted(skip))}")
    pick = sorted(band3, key=lambda c: (-c["spec"], [-(v or 0) for v in c["score"]]))[0]
    top = band3[0]
    print("\n" + "=" * 80)
    print(f"  PICK: {pick['item_id']}  score={pick['score']}  spec={pick['spec']} [{', '.join(pick['sigs'])}]")
    print(f"    {pick['desc']}")
    if pick is not top:
        print(f"\n    NOTE: specificity overrode the metric (top-ranked was {top['item_id']},")
        print(f"          spec {top['spec']}). Override confined to the top {TIEBREAK_BAND}.")
    print("=" * 80 + "\n")
    if a.commit:
        commit_pick(a.vertical, pick, eligible.index(pick) + 1)
    else:
        print("  (dry run - add --commit <item_id> to record it)\n")


if __name__ == "__main__":
    main()
