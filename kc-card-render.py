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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-08-07)
CARDS = [
 # --- Commodity (mandi_bhav) — 2 tejii/RED (Masoor in-house, Besan MP) + 1 mandi/GREEN (Sarson tel in-house) for balance ---
 dict(i=1, label="मंडी भाव", stripe=RED, headline="मसूर दाल",
   price=f'{tri("up",RED)}₹6,875<span class="unit">/क्विंटल</span>',
   sub=f'देसी मसूर ₹25 तेज होकर दिल्ली ₹6,850–6,875/क्विंटल; छोटी मसूर की भारी किल्लत, कच्चा माल ₹80–85/किलो · <b class="delta" style="color:{RED}">+₹25/क्विंटल</b>',
   l1="क्यों", v1="मूंगावली–सागर–भोपाल लाइन से आवक घटी; छोटी मसूर की किल्लत, पड़ते का अभाव",
   l2="क्या करें", v2="माल दबाकर रखने के बजाय दाल बनवाकर बेचने में फायदा; देसी ₹6,850 के आसपास"),
 dict(i=2, label="मंडी भाव", stripe=GREEN, headline="सरसों तेल",
   price=f'{tri("down",GREEN)}₹16,800<span class="unit">/क्विंटल</span>',
   sub=f'सरसों तेल ₹50 टूटकर ₹16,800/क्विंटल (दादरी ₹16,700); जुलाई खाद्य तेल आयात +34% यानी ~14.9 लाख टन, 10 महीने का ऊंचा · <b class="delta" style="color:{GREEN}">−₹50/क्विंटल</b>',
   l1="क्यों", v1="मिलों की खरीद कमजोर; त्योहार से पहले कंपनियों ने गोदाम भर लिए, माल की कमी नहीं",
   l2="क्या करें", v2="भाव सीमित दायरे में रहेगा; पुराने ऊंचे भाव का स्टॉक जल्दी निकालें, बड़ा स्टॉक न भरें"),
 dict(i=3, label="मंडी भाव", stripe=RED, headline="बेसन",
   price=f'{tri("up",RED)}₹80<span class="unit">/किलो</span>',
   sub=f'बेसन ₹4 तेज होकर ₹80/किलो; Samrat कट्टा ₹800/10 किलो (पहले ₹760); मिल आपूर्ति घटी व त्योहारी मांग · <b class="delta" style="color:{RED}">+₹4/किलो</b>',
   l1="क्यों", v1="मिलों की आपूर्ति घटी और त्योहारी मांग बढ़ी; आगे भी तेजी की संभावना",
   l2="क्या करें", v2="त्योहारी सीजन से पहले जरूरत का स्टॉक अभी भर लें—भाव और चढ़ सकते हैं"),
 # --- FMCG (fmcg) — top 3 by Like Rate desc across ALL 4 segments after ledger dedup (news_id + 7-day brand) + body-verify ---
 #     Bakemate Cofe Town 6.48, Clean & Clear facewash 6.46, Supermax blade 5.90 — all Retailer Scheme, distinct categories (confectionery / personal-care / shaving), all clean free-goods mechanics.
 #     SKIPPED news_id-dup (12d ledger): Hajmola chatkola 6.61, 7-Star Kamal 6.49, Tata Soulfull. SKIPPED 7d brand: Cadbury 5Star x2, Patanjali brush/paste, Vicks, Close-Up x2, Dabar Red, Royal Dairy x2, Kaccha Mango, Babool. SKIPPED body-reject/no-figure: Eno(offer-only), Godrej hair-colour(packaging only). SKIPPED oral-care over-cover(soft): Colgate ₹10/₹20.
 dict(i=4, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="कॉफ़ी टाउन टॉफ़ी",
   price='<span class="offer" style="background:%s">डब्बे पर 1 बाउल फ्री</span>'%SCHEME_GREEN,
   sub='बेकमेट कॉफ़ी टाउन टॉफ़ी—एक डब्बे में 220 टॉफ़ी, लागत ₹165.44; साथ में एक बाउल बिल्कुल फ्री · <b class="delta">1 बाउल फ्री</b>',
   l1="स्कीम", v1="220 टॉफ़ी वाला डब्बा (लागत ₹165) खरीदने पर एक बाउल फ्री",
   l2="फायदा", v2="हर डब्बे पर फ्री बाउल गिफ्ट—बच्चों में तेज बिकने वाली ₹1 टॉफ़ी"),
 dict(i=5, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="क्लीन एंड क्लियर",
   price='<span class="offer" style="background:%s">जार पर 11+1 फ्री</span>'%SCHEME_GREEN,
   sub='क्लीन एंड क्लियर फेसवॉश ₹30 बिक्री—1 जार में 11+1 पीस फ्री (12 पीस); होलसेल ₹278, मार्जिन ₹52+30 · <b class="delta">मार्जिन ₹52+30</b>',
   l1="स्कीम", v1="₹30 बिक्री वाला फेसवॉश—1 जार में 11+1 फ्री, होलसेल ₹278/12 पीस",
   l2="फायदा", v2="₹52+30 का मार्जिन और अच्छी डिमांड—फास्ट मूविंग पर्सनल केयर"),
 dict(i=6, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="सुपरमैक्स ब्लेड",
   price='<span class="offer" style="background:%s">डिब्बे पर 5 ब्लेड फ्री</span>'%SCHEME_GREEN,
   sub='सुपरमैक्स स्टेनलेस ब्लेड—50 पीस डिब्बा अब 55 पीस (5 फ्री); होलसेल ₹90, ₹3/ब्लेड = ₹165 बिक्री, मार्जिन ₹75 · <b class="delta">मार्जिन ₹75</b>',
   l1="स्कीम", v1="50 पीस का डिब्बा अब 55 पीस—5 ब्लेड फ्री, होलसेल ₹90",
   l2="फायदा", v2="55×₹3 = ₹165 बिक्री, ₹75 का मार्जिन प्रति डिब्बा"),
 # --- News (trending_news) — RBI repo-rate hold (in-house policy, direct shopkeeper-loan impact; scam/fraud bait & रुझान digests SKIPPED; Stand-Up India loan skipped as too-similar to 08-05/08-06 loan scheme) ---
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="रेपो रेट स्थिर",
   price='<span class="news">RBI ने ब्याज दर 5.25% पर रोकी</span>',
   sub='रिजर्व बैंक ने रेपो रेट 5.25% पर बरकरार रखी—दुकान/गाड़ी/घर कर्ज की किस्त अभी नहीं बढ़ेगी; महंगाई अनुमान ~5%, विकास दर 6.7% · <b class="delta">किस्त स्थिर</b>',
   l1="क्यों ज़रूरी", v1="रेपो वही दर है जिस पर बैंक कर्ज देते हैं; दर न बढ़ने से कर्ज की किस्त महंगी नहीं होगी",
   l2="क्या करें", v2="त्योहारी माल भरने की योजना बनाएं—दुकान का कर्ज व कैश लिमिट अभी महंगी नहीं"),
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
