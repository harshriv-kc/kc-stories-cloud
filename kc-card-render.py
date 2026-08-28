# -*- coding: utf-8 -*-
"""
KC STORIES — DETERMINISTIC CARD COMPOSITOR (the fix for inconsistent text)
==========================================================================
WHY: Gemini cannot render Devanagari at consistent fixed sizes — headlines drift
card-to-card and oversize until they clip (the गुड़ bug). PIL can't shape Devanagari
(no raqm/libraqm on this box). So we render the card OURSELVES from a locked HTML/CSS
template using headless Edge + the 'Nirmala UI' font (which shapes Devanagari perfectly).
Gemini now supplies ONLY the photo; every text element is pixel-identical on every card.

PIPELINE (replaces the old "generate full card + layout-lock + stripe-lock"):
  1. Gemini generates ONE PHOTO per card (still-life, NO text, NO bands) via
     generate_story_image(aspect="portrait"). Photo prompt = subject on dark weathered
     wood, soft daylight upper-left, slightly desaturated wire-photo look, no people,
     no text/labels. FMCG: the real brand pack legible. Commodity/news: generic, no brands.
     Save each as photo_<i>.png (any portrait-ish crop works; object-fit:cover handles it).
     (You may also crop the photo band out of a previously-generated card if reusing art.)
  2. Fill the CARDS list below with the 7 cards' data and run this script. It writes
     card_<i>.png at 1080x1920 — masthead label, gold rule, photo, cream panel, left
     stripe and ALL text rendered at fixed sizes. No layout-lock/stripe-lock needed.
  3. Upload each card_<i>.png via jack:upload_image(blob="news").
     ⚠ nginx caps uploads at ~1MB. If a PNG is >1MB it returns HTTP 413 — resize to
     1000px wide and re-save (im.resize((1000,1778))) to get under the cap, then it
     converts to .webp like the rest. Use the returned URL as the slide img_url.

REQUIREMENTS: Windows 'Nirmala UI' font (C:/Windows/Fonts) + msedge. Both preinstalled.
Run: PYTHONIOENCODING=utf-8 python3 kc-card-render.py   (set HERE to the working dir)

DIRECTION COLOURS: तेज़ी RED #9A2828 · मंदी GREEN #1E7A3C · FMCG/news BLACK #1A1A1A.
The stripe + commodity triangle + sub-line delta all use the direction colour.
Triangle: "up" = ▲ तेज़ी, "down" = ▼ मंदी (drawn with CSS borders, never a glyph).
Price line: commodity = tri()+₹X+unit · FMCG = ₹X →(grey) ₹Y · news = <span class="news">summary</span>.
"""
import base64, subprocess, os, shutil, glob
from PIL import Image

# Cross-platform Chromium/Chrome finder. CLOUD = Linux: prefer CHROME_BIN (setup.sh exports a VERIFIED working
# binary), then the pre-installed Playwright chromium. NOTE: /usr/bin/chromium-browser is a BROKEN snap stub in
# the sandbox (exists but errors) — do NOT prefer it. Nirmala UI comes from fonts/Nirmala.ttc. LOCAL = Windows.
_CANDS = [
    os.environ.get("CHROME_BIN", ""),
    *sorted(glob.glob("/opt/pw-browsers/chromium*/chrome-linux/chrome"), reverse=True),
    *sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium*/chrome-linux/chrome")), reverse=True),
    shutil.which("google-chrome"), shutil.which("google-chrome-stable"), shutil.which("chromium"),
    "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
EDGE = next((p for p in _CANDS if p and os.path.exists(p)), _CANDS[0])
HERE = os.environ.get("KC_DIR", os.getcwd())   # dir holding photo_<i>.png; card_<i>.png written here
_PROFILE = os.path.join(HERE, ".browser_profile")   # clean isolated profile so launches never attach to a running browser

RED="#9A2828"; GREEN="#1E7A3C"; BLACK="#1A1A1A"; GREY="#7A7A7A"
# FMCG segment accents (stripe + pill). Segment is decided by the post's report bucket, NOT by us.
# ALL FMCG cards set eyebrow="FMCG" (gold eyebrow over the heading); label = the SHORT segment name below:
#   scheme→Retailer Scheme  -> eyebrow="FMCG" label="व्यापारी स्कीम"      stripe SCHEME_GREEN  rep = offer pill (free-goods)        grid स्कीम/फायदा
#   scheme→Consumer Scheme  -> eyebrow="FMCG" label="ग्राहक ऑफर"          stripe SCHEME_BLUE   rep = offer pill (combo ratio)       grid ऑफर/ग्राहक को
#   new_product_launch      -> eyebrow="FMCG" label="नया प्रोडक्ट लॉन्च"   stripe LAUNCH_AMBER  rep = <span class="newtag">नया</span> + MRP  grid नया क्या/फायदा
#   fmcg_product_change     -> eyebrow="FMCG" label="प्रोडक्ट बदलाव"       stripe BLACK         rep = ₹X→₹Y or 110g→100g (ARROW — this segment ONLY)  grid बदलाव/फायदा
# (commodity/news cards omit eyebrow -> single large heading "मंडी भाव" / "ट्रेंडिंग न्यूज़")
# offer pill: '<span class="offer" style="background:SCHEME_GREEN|SCHEME_BLUE">…</span>' · newtag: '<span class="newtag" style="background:LAUNCH_AMBER">नया</span><span class="mrp">MRP ₹X</span>'
SCHEME_GREEN="#1E7A3C"; SCHEME_BLUE="#1F5AA6"; LAUNCH_AMBER="#C8772A"

def tri(direction, color):
    if direction == "up":
        return f'<span class="tri" style="border-left:26px solid transparent;border-right:26px solid transparent;border-bottom:42px solid {color}"></span>'
    return f'<span class="tri" style="border-left:26px solid transparent;border-right:26px solid transparent;border-top:42px solid {color}"></span>'

def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-08-27)
CARDS = [
 # --- Commodity (mandi_bhav) — 2 मंदी/GREEN + 1 तेजी/RED (balance; recent days RED-heavy). चीनी / सोया तेल / लौंग. In-house 27अग (distinct news_ids). ---
 dict(i=1, label="मंडी भाव", stripe=RED, headline="गेहूं",
   price=f'{tri("up",RED)}₹2,945–2,950<span class="unit">/क्विंटल</span>',
   sub=f'चक्की गेहूं ₹2,945–2,950/क्विंटल, एक सप्ताह में ₹80–90 चढ़ा; निर्यात छूट से फ्लोर मिलों की खरीद तेज · <b class="delta" style="color:{RED}">₹80–90 तेजी</b>',
   l1="क्यों", v1="सरकार ने खुले में गेहूं निर्यात की छूट दी, मिलों की खरीद अचानक तेज हुई",
   l2="क्या करें", v2="₹3,000/क्विंटल बनते ही एक बार माल बेच लें; NCR मंडियों में ₹40–50 और तेजी संभव"),
 dict(i=2, label="मंडी भाव", stripe=RED, headline="देसी चना",
   price=f'{tri("up",RED)}₹6,375<span class="unit">/क्विंटल</span>',
   sub=f'बढ़िया देसी चना ₹6,350–6,375/क्विंटल पर टिका, चना दाल ₹7,200–7,550; आवक कम, आगे ~₹500 तेजी के संकेत · <b class="delta" style="color:{RED}">₹500 संभावित तेजी</b>',
   l1="क्यों", v1="राजस्थान-कर्नाटक-MP मंडियों में आवक हल्की, दाल मिलों को जरूरत का चना नहीं मिल रहा",
   l2="क्या करें", v2="महीने भर का चना व बेसन अभी उठा लें; त्योहारों में बेसन खपत बढ़ने से भाव ऊपर जाएंगे"),
 dict(i=3, label="मंडी भाव", stripe=GREEN, headline="इलायची",
   price=f'{tri("down",GREEN)}₹2,600–2,900<span class="unit">/किलो</span>',
   sub=f'छोटी इलायची ₹100–150 टूटकर ₹2,600–2,900/किलो; नीलामी औसत घटकर ₹2,924, हल्दी भी नरम · <b class="delta" style="color:{GREEN}">₹150 गिरावट</b>',
   l1="क्यों", v1="दक्षिण की नीलामी में आवक बनी हुई, ग्राहकी कमजोर और मुनाफा वसूली जारी",
   l2="क्या करें", v2="त्योहारी इलायची-हल्दी का महीने भर का माल अभी सस्ते में भर लें, सितंबर से महंगा पड़ेगा"),
 # --- FMCG (fmcg) — TOP 3 by LR desc after ledger dedup (news_id 12d + 7d brand HARD) + body-verify. Spread: personal-care/confectionery/puja; segments Consumer/Retailer/Consumer. ---
 #     santoor LR7.45 (Consumer, B1G1 200ml, MRP105/buy75/Rs30), ankit-wafer LR5.73 (Retailer, Rs2 jar +Rs5 free, MRP200/buy150/Rs50), sweet-night LR5.71 (Consumer, 12+1 pouch, MRP156/buy115/Rs41).
 #     BLOCKED 7d brand/newsid dedup: apsara-pencil, vim, close-up, zed-black, natraj-pencil, cadbury, dabur-red, lux, dermicool, navratna, all-out, colgate, sesa, stamp.
 dict(i=4, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="सैंटूर हैंडवॉश",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">1 पर 1 फ्री · 200ml</span>',
   sub='सैंटूर क्लासिक हैंडवॉश (सैंडलवुड-तुलसी) 200ml—Buy 1 Get 1 फ्री; कुल MRP ₹105, खरीद ₹75 · <b class="delta">₹30 मार्जिन</b>',
   l1="ऑफर", v1="200ml पर 200ml बिल्कुल फ्री—दो बोतल ₹105 में",
   l2="ग्राहक को", v2="एक के दाम में दो हैंडवॉश; तेज बिकने वाला ऑफर, ₹30 सीधा मार्जिन"),
 dict(i=5, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="अंकित चोको वेफर",
   price=f'<span class="offer" style="background:{SCHEME_GREEN}">जार पर ₹5 माल फ्री</span>',
   sub='अंकित चोको वेफर ₹2 जार—खरीदने पर ₹5 का माल जार के अंदर फ्री; कुल MRP ₹200, खरीद ₹150 · <b class="delta">₹50 मार्जिन</b>',
   l1="स्कीम", v1="₹2 वेफर जार पर ₹5 का माल फ्री (जार के अंदर)",
   l2="फायदा", v2="₹50 डायरेक्ट मार्जिन; ₹2 इम्पल्स आइटम, बच्चों में तेज बिक्री"),
 dict(i=6, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="स्वीट नाईट अगरबत्ती",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">12 पर 1 फ्री</span>',
   sub='आमिर स्वीट नाईट सिट्रोनेला अगरबत्ती—12 खरीदने पर 1 पाउच (₹12) फ्री; कुल MRP ₹156, खरीद ₹115 · <b class="delta">₹41 मार्जिन</b>',
   l1="ऑफर", v1="12 पर 1 पाउच मुफ्त, ₹12 का माल फ्री",
   l2="ग्राहक को", v2="मच्छर भगाने वाली अगरबत्ती; त्योहार-सीजन में मांग तेज, ₹41 मार्जिन"),
 # --- News (trending_news) — प्याज बफर स्टॉक: सरकार ₹35/किलो बेच रही (in-house 28अग; policy/market-impact, concrete, non-bait, actionable). मिलावट-छापा bait skipped. ---
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="प्याज",
   price='<span class="news">सरकार बफर स्टॉक से ₹35/किलो प्याज बेच रही</span>',
   sub='खुदरा प्याज ₹55–60/किलो, देश का औसत ₹37.87; NCCF-NAFED की दुकान व वैन पर ₹35, बफर 62,000 टन · <b class="delta">सप्लाई बढ़ेगी</b>',
   l1="क्यों ज़रूरी", v1="त्योहार से पहले दाम चढ़े, सरकार ने बफर से बिक्री शुरू की; आगे थोक भाव नरम पड़ेंगे",
   l2="क्या करें", v2="ज्यादा प्याज न भरें—हफ्ते भर का माल रखें, प्याज जल्दी सड़ता है और पैसा डूबता है"),
]
TPL = '''<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;width:1080px;height:1920px;overflow:hidden;font-family:'Nirmala UI','Segoe UI',sans-serif;}}
.card{{width:1080px;height:1920px;position:relative;background:#FAFAF7;}}
.mast{{height:300px;background:#14181F;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;padding-left:80px;box-sizing:border-box;}}
.eyebrow{{font-size:40px;font-weight:700;color:#C8A24A;letter-spacing:8px;margin-bottom:10px;}}  /* FMCG-only eyebrow; keeps the long segment heading from spanning the whole masthead */
.lbl{{font-size:78px;font-weight:700;color:#F2EDDF;letter-spacing:2px;line-height:1.0;}}
.gold{{height:4px;background:#C8A24A;}}
.photo{{height:700px;width:1080px;overflow:hidden;}}
.photo img{{width:1080px;height:700px;object-fit:cover;object-position:center;display:block;}}
.panel{{position:relative;height:916px;background:#FAFAF7;box-sizing:border-box;padding:0 80px 0 150px;}}
.stripe{{position:absolute;left:0;top:0;bottom:0;width:18px;background:{stripe};}}
/* Content is TOP-ANCHORED (flex-start), NOT centred. Centring overflowed equally top+bottom,
   so tall cards (3+ wrapped lines) pushed the headline UP into the photo (the overlap bug).
   flex-start guarantees the headline always sits just below the photo; any overflow grows
   DOWN into the panel. Photo trimmed to 700 / panel raised to 916 so even the tallest card
   (1-line headline + price + 2-line sub + two 2-line grid rows ~610px) clears the bottom
   ~190px CTA reserve. NEVER set a fixed .content height with justify-content:center again. */
.content{{padding-top:30px;display:flex;flex-direction:column;justify-content:flex-start;box-sizing:border-box;}}
.headline{{font-size:100px;font-weight:700;color:#1A1A1A;line-height:1.05;margin:0 0 12px 0;}}
.price{{font-size:62px;font-weight:700;color:#1A1A1A;margin:0;display:flex;align-items:center;line-height:1.1;flex-wrap:wrap;gap:6px 0;}}
.price .unit{{font-size:38px;font-weight:400;color:#7A7A7A;margin-left:8px;}}
.price .arrow{{color:#7A7A7A;margin:0 24px;font-weight:400;}}
.price .news{{font-size:56px;}}
.tri{{width:0;height:0;display:inline-block;margin-right:18px;}}
/* FMCG scheme/launch representations (NOT product-change): offer pill + new-launch pill */
.offer{{display:inline-block;font-size:50px;font-weight:700;color:#fff;padding:10px 30px;border-radius:14px;line-height:1.15;}}
.newtag{{display:inline-block;font-size:46px;font-weight:700;color:#fff;padding:8px 28px;border-radius:14px;margin-right:24px;}}
.mrp{{font-size:60px;font-weight:700;color:#1A1A1A;}}
.wt{{font-size:62px;font-weight:700;color:#1A1A1A;}}
.sub{{font-size:37px;color:#7A7A7A;margin-top:22px;line-height:1.34;}}
.sub .delta{{font-weight:700;color:#1A1A1A;}}
.grid{{margin-top:28px;}}
.row{{display:flex;padding:20px 0;align-items:flex-start;}}
.row.b{{border-top:1px solid #E8E2D2;}}
.lab{{width:250px;font-size:31px;font-weight:700;color:#7A7A7A;letter-spacing:1px;flex-shrink:0;}}
.val{{flex:1;font-size:40px;color:#1A1A1A;line-height:1.22;}}
</style></head><body><div class="card">
<div class="mast">{eyebrow_html}<div class="lbl">{label}</div></div>
<div class="gold"></div>
<div class="photo"><img src="data:image/png;base64,{img}"></div>
<div class="panel"><div class="stripe"></div><div class="content">
<div class="headline">{headline}</div>
<div class="price">{price}</div>
<div class="sub">{sub}</div>
<div class="grid">
<div class="row"><div class="lab">{l1}</div><div class="val">{v1}</div></div>
<div class="row b"><div class="lab">{l2}</div><div class="val">{v2}</div></div>
</div></div></div></div></body></html>'''

def render():
    for c in CARDS:
        c["img"] = b64(os.path.join(HERE, f'photo_{c["i"]}.png'))
        ev = c.get("eyebrow", "")            # FMCG cards set eyebrow="FMCG"; commodity/news leave it empty
        c["eyebrow_html"] = f'<div class="eyebrow">{ev}</div>' if ev else ''
        html = TPL.format(**c)
        hp = os.path.join(HERE, f'card_{c["i"]}.html')
        op = os.path.join(HERE, f'card_{c["i"]}.png')
        with open(hp, "w", encoding="utf-8") as f:   # MUST flush+close before Edge reads it; a bare open().write() races and Edge screenshots a blank/missing page
            f.write(html); f.flush(); os.fsync(f.fileno())
        if os.path.exists(op):
            os.remove(op)
        for _attempt in range(3):
            subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                "--no-first-run", "--no-default-browser-check", f"--user-data-dir={_PROFILE}",
                "--force-device-scale-factor=1", f"--screenshot={op}",
                "--window-size=1080,1920", hp], capture_output=True)
            if os.path.exists(op):
                break
        # keep upload under the ~1MB nginx cap
        if os.path.exists(op) and os.path.getsize(op) > 1_000_000:
            Image.open(op).convert("RGB").resize((1000, 1778)).save(op, optimize=True)
        print("card", c["i"], "->", os.path.exists(op), os.path.getsize(op) if os.path.exists(op) else "FAIL")

if __name__ == "__main__":
    render()
