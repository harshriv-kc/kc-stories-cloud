# -*- coding: utf-8 -*-
"""
KC PUSH-NOTIFICATION SCHEDULER
==============================
Schedules a WebEngage push via the d2r notification pipeline, using the audience +
fixed key-values stored in specs/pn-campaign-registry.json.

DRY-RUN BY DEFAULT. Nothing is sent unless you pass --send.

  # see exactly what would be posted
  python3 pn-schedule.py --type youtube_videos_shop_tips \
      --entity <item-uuid> --nd out/<key>.json --time "2026-08-14 15:30"

  # same, but restricted to an internal test segment (SAFE first live run)
  python3 pn-schedule.py --type youtube_videos_shop_tips ... --test-segment ~8bel1kj --send

WHY THE GUARDS EXIST (all verified against production, 2026-08-13):
 * The pipeline returns HTTP 500 *after* the campaign is already created+activated
   (Samachar: 242/242 rows with NULL campaign_id). So a failure response does NOT mean
   "not sent". THIS SCRIPT NEVER RETRIES. On error it tells you to check the dashboard.
 * There is no cancel/delete API. Schedule with lead time so you can still kill it in
   the WebEngage UI. --send refuses anything less than MIN_LEAD_MIN minutes out.
 * A create also PUTs its variations over every journey campaign sharing its campaignType.
   We therefore force an UNMAPPED campaignType. Never set this to Samachar/Rujhan/etc.
 * notification_data must be a STRINGIFIED JSON string; an object silently degrades the
   push to plain text. Validated below.
 * isSticky must stay false: sticky injects a CTA that overrides multi_icon per-badge
   deep_links (and campaign ~1dng34j deliberately has an EMPTY on-click action).
"""
import argparse, json, os, sys, subprocess, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY = os.path.join(HERE, "specs", "pn-campaign-registry.json")
LEDGER = os.path.join(HERE, "pn-schedule-log.json")
ENDPOINT = "https://asia-south1-op-d2r.cloudfunctions.net/d2r_notification_automation"

# campaignType MUST NOT appear in the cloud function's CAMPAIGN_TYPE_ID_MAPPING,
# or this send silently rewrites up to 17 unrelated live journey campaigns.
SAFE_CAMPAIGN_TYPE = "Others"
JOURNEY_MAPPED = {"Samachar", "Rujhan", "Shakkar", "Soya Tel", "Other Commodity",
                  "Dal", "Trending News 1", "Trending News 2", "government schemes"}
MIN_LEAD_MIN = 45


def die(msg):
    print(f"\n  ABORT: {msg}\n")
    sys.exit(1)


def load_registry():
    with open(REGISTRY, encoding="utf-8") as f:
        return json.load(f)


def validate_notification_data(nd_str, template_type):
    """notification_data must be a STRING containing valid JSON, on ONE line.

    ⚑ WebEngage's key-value field REJECTS multi-line values (it flags the field red
    and the campaign is unusable). The PN image kit writes its JSON pretty-printed
    with indent=2, so passing that file through verbatim produces an invalid campaign
    (hit for real on campaign ~gie2jn, 2026-08-13). We therefore always RE-SERIALIZE
    compactly here rather than trusting the caller's formatting.
    """
    if not isinstance(nd_str, str):
        die("notification_data must be a STRING, not an object "
            "(an object silently degrades the push to plain text).")
    try:
        parsed = json.loads(nd_str)
    except Exception as e:
        die(f"notification_data is not parseable JSON: {e}")
    if template_type == "multi_icon":
        imgs = parsed.get("images")
        if not isinstance(imgs, list) or not imgs:
            die("multi_icon notification_data.images must be a non-empty array")
        if len(imgs) > 3:
            die(f"multi_icon supports max 3 images, got {len(imgs)}")
        for i, im in enumerate(imgs):
            if not im.get("url"):
                die(f"images[{i}] has no url")
    elif template_type == "duo_image":
        for k in ("expanded_image", "collapsed_image"):
            if not parsed.get(k):
                die(f"duo_image notification_data missing {k}")
    # single-line compact form — see docstring
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def build_payload(cfg, entity, nd_str, when_epoch, tags, test_segment=None):
    tt = cfg["kvPairs_fixed"]["template_type"]
    nd_compact = validate_notification_data(nd_str, tt)   # normalised to ONE line

    kv = dict(cfg["kvPairs_fixed"])
    kv["notification_data"] = nd_compact
    if "entity" in cfg["kvPairs_per_send"]:
        if not entity:
            die(f"campaign type '{cfg['label']}' requires --entity (the item id used for redirection)")
        kv["entity"] = entity

    seg = json.loads(json.dumps(cfg["segments"]))  # deep copy
    if test_segment:
        seg["includedSegments"] = [test_segment]
        seg["includedSegmentsOperator"] = "OR"
        seg["excludedSegments"] = []

    return {
        "path": "create_notification",
        "service": "webengage",
        "env": "PROD",
        "data": {
            "campaignName": cfg["label"],
            "campaignType": SAFE_CAMPAIGN_TYPE,
            "campaignTags": tags,
            "segments": seg,
            "sendNow": False,
            "scheduledTime": when_epoch,
            "titles": [cfg.get("title", "Kirana Club")],
            "messages": [cfg.get("description", "\U0001F525")],
            "kvPairs": kv,
            "isSticky": False,
            "launchNotification": True,
        },
    }


def ledger_check_and_reserve(key, dry):
    """Idempotency: the API has NO dedupe and duplicate live campaigns have shipped before."""
    log = {"runs": []}
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as f:
            log = json.load(f)
    if any(r["key"] == key for r in log["runs"]):
        die(f"'{key}' already scheduled (see pn-schedule-log.json). Refusing to double-send.")
    if not dry:
        log["runs"].append({"key": key, "at": datetime.datetime.utcnow().isoformat() + "Z"})
        with open(LEDGER, "w", encoding="utf-8") as f:
            json.dump(log, f, ensure_ascii=False, indent=2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", required=True)
    p.add_argument("--entity", default=None, help="item id for redirection (duo_image types)")
    p.add_argument("--nd", required=True, help="path to the notification_data JSON file")
    p.add_argument("--time", required=True, help='IST, "YYYY-MM-DD HH:MM"')
    p.add_argument("--test-segment", default=None, help="override audience with ONE segment id")
    p.add_argument("--send", action="store_true", help="actually schedule (default = dry run)")
    a = p.parse_args()

    reg = load_registry()
    if a.type not in reg["campaign_types"]:
        die(f"unknown type. Available: {', '.join(reg['campaign_types'])}")
    cfg = reg["campaign_types"][a.type]

    if SAFE_CAMPAIGN_TYPE in JOURNEY_MAPPED:
        die("SAFE_CAMPAIGN_TYPE is journey-mapped — would rewrite other live campaigns.")

    with open(a.nd, encoding="utf-8") as f:
        nd_str = f.read().strip()

    dt = datetime.datetime.strptime(a.time, "%Y-%m-%d %H:%M")
    epoch = int((dt - datetime.datetime(1970, 1, 1)).total_seconds()) - 19800  # IST -> UTC
    lead = (dt - (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)))
    lead_min = lead.total_seconds() / 60

    payload = build_payload(cfg, a.entity, nd_str, epoch, cfg["campaignTags"], a.test_segment)
    key = f"{a.type}|{a.time}"

    print("=" * 72)
    print(f"  CAMPAIGN : {cfg['label']}")
    print(f"  TEMPLATE : {cfg['kvPairs_fixed']['template_type']}")
    print(f"  WHEN     : {a.time} IST  (lead {lead_min:.0f} min)")
    aud = payload["data"]["segments"]
    print(f"  INCLUDE  : {aud['includedSegments']}  [{aud['includedSegmentsOperator']}]")
    print(f"  EXCLUDE  : {aud['excludedSegments']}  [{aud['excludedSegmentsOperator']}]")
    print(f"           + FORCED by pipeline: ['~48clbl2', '~1i5j875']")
    if a.test_segment:
        print(f"  ** TEST SEGMENT OVERRIDE ACTIVE -> {a.test_segment} **")
    print("=" * 72)
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:2600])
    print("=" * 72)

    if not a.send:
        print("\n  DRY RUN — nothing sent. Add --send to schedule.\n")
        return

    if lead_min < MIN_LEAD_MIN:
        die(f"lead time {lead_min:.0f} min < {MIN_LEAD_MIN}. There is NO cancel API — "
            "you need a window to kill it in the WebEngage UI.")

    ledger_check_and_reserve(key, dry=False)
    print("\n  SENDING (no retry on failure — see header)...\n")
    r = subprocess.run(["curl", "-sS", "-X", "POST", ENDPOINT,
                        "-H", "Content-Type: application/json",
                        "-d", json.dumps(payload, ensure_ascii=False),
                        "-w", "\nHTTP:%{http_code}"],
                       capture_output=True, text=True, timeout=120)
    print(r.stdout[-1500:])
    if "HTTP:200" not in r.stdout:
        print("\n  !! NON-200. The campaign may STILL BE LIVE (known pipeline behaviour).")
        print("     DO NOT re-run. Check the WebEngage dashboard before doing anything.\n")


if __name__ == "__main__":
    main()
