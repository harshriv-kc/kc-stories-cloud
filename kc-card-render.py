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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-09-11 · experiment window CLOSED → base 3+3+1)
CARDS = [
 # --- Commodity (mandi_bhav) — 2 तेजी/RED + 1 मंदी/GREEN (balance). गोला (in-house Samachar 11सित, तेजी +₹1000, गणेश चतुर्थी demand) + मूंग (in-house दाल 11सित, तेजी +₹100) + बासमती चावल (in-house चावल 11सित, मंदी −₹100–200, नई फसल दबाव). All in-house today; distinct news_ids. ---
 dict(i=1, label="मंडी भाव", stripe=RED, headline="गोला",
   price=f'{tri("up",RED)}₹38,000–46,000<span class="unit">/क्विंटल</span>',
   sub=f'सूखा नारियल (गोला) एक ही दिन ₹1,000 उछलकर ₹38,000–46,000/क्विंटल; गोला बुरादा भी ₹50 तेज होकर ₹7,350–7,550/25 किलो — गणेश चतुर्थी की त्योहारी मांग · <b class="delta" style="color:{RED}">₹1,000 तेजी</b>',
   l1="क्यों", v1="बिकवाली कमजोर और गणेश चतुर्थी की त्योहारी ग्राहकी निकलने से मेवा बाजार में गोला तेज",
   l2="क्या करें", v2="गोला-मेवा का त्योहारी माल अभी भर लें — 14 सितंबर को गणेश चतुर्थी, आगे भाव और चढ़ सकते"),
 dict(i=2, label="मंडी भाव", stripe=RED, headline="मूंग",
   price=f'{tri("up",RED)}₹7,700–8,400<span class="unit">/क्विंटल</span>',
   sub=f'चमकी मूंग ₹100 तेज — जयपुर ₹7,700, अकोला ₹8,400/क्विंटल; दिल्ली में MP मूंग ₹7,850–8,300 — अच्छी किस्म का माल कम आ रहा · <b class="delta" style="color:{RED}">₹100 तेजी</b>',
   l1="क्यों", v1="उड़द-अरहर में ग्राहकी सुस्त पर मूंग में बढ़िया किस्म का माल कम; अकोला-रायपुर में अच्छा उठाव",
   l2="क्या करें", v2="मूंग-मूंग दाल का 2–3 हफ्ते का माल उठाएं; राजस्थान की नई फसल आते ही भाव ₹8,200 के आसपास ठहर सकते"),
 dict(i=3, label="मंडी भाव", stripe=GREEN, headline="बासमती चावल",
   price=f'{tri("down",GREEN)}₹9,900–10,000<span class="unit">/क्विंटल</span>',
   sub=f'बासमती ₹100–200 टूटा — 1121 सेला ₹9,900–10,000, 1509 सेला ₹7,600–7,800/क्विंटल; परमल भी ₹100 घटकर ₹4,100–4,200 — मांग सुस्त, नई फसल का दबाव · <b class="delta" style="color:{GREEN}">₹200 गिरावट</b>',
   l1="क्यों", v1="निर्यात-घरेलू दोनों मांग सुस्त और मिलों की बिकवाली बढ़ी; हरियाणा-पंजाब में 1509 की नई फसल उतरने लगी",
   l2="क्या करें", v2="त्योहारी बिक्री का बासमती घटे भाव पर उठा लें; बड़ा भंडार न भरें — बारीक चावल ₹8,500 तक और नरम हो सकता"),
 # --- FMCG (fmcg) — TOP 3 by LR desc across all 4 segments after ledger dedup (news_id 12d + brand 7d) + body-verify (concrete number). Real product photos, brands legible. ---
 #     mountain-dew LR8.09 (Consumer, 1L+250ml free), glow-lovely LR7.91 (product_change, ₹62→₹72 rate hike), sunfeast LR7.72 (Consumer, 2×₹5 + ₹5 pencil free — chosen over aakash LR7.81 to avoid मूंग overlap + category spread).
 #     SWAPPED OUT (Step 6 body-verify): global-soap LR9.75 (bare "4+1" ratio, no ₹/MRP/weight, vague 'Global' brand → hyper-local risk). BLOCKED brand 7d: colgate×3/ghadi×2/patanjali-ghee/patanjali-dant-kranti/lifebuoy/dabur-red. Category spread: beverage / personal-care / biscuit.
 dict(i=4, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="माउंटेन ड्यू",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">1L पर 250ml फ्री</span>',
   sub='माउंटेन ड्यू 1 लीटर बोतल के साथ 250ml एक्स्ट्रा बिल्कुल फ्री — रेट में कोई बदलाव नहीं; त्योहारी-गर्मी में तेज बिकने वाला ठंडा पेय · <b class="delta">250ml फ्री</b>',
   l1="ऑफर", v1="1 लीटर माउंटेन ड्यू पर 250ml एक्स्ट्रा फ्री, वही पुराना रेट",
   l2="ग्राहक को", v2="उतने ही दाम में सवा लीटर पेय; ग्राहक को ज्यादा माल का फायदा, काउंटर पर तेज बिक्री"),
 dict(i=5, eyebrow="FMCG", label="प्रोडक्ट बदलाव", stripe=BLACK, headline="ग्लो एंड लवली",
   price='₹62<span class="arrow">→</span>₹72',
   sub='फेयर एंड लवली (अब ग्लो एंड लवली) क्रीम का रेट ₹62 से बढ़कर ₹72 — ₹10 की रेट हाइक; रोज बिकने वाला पर्सनल-केयर आइटम · <b class="delta">₹10 महंगी</b>',
   l1="बदलाव", v1="ग्लो एंड लवली फेयरनेस क्रीम का भाव ₹62 से ₹72 हुआ (₹10 बढ़ा)",
   l2="फायदा", v2="पुराने ₹62 वाले स्टॉक को पुराने MRP पर बेचें — नए भाव से सीधा ज्यादा मार्जिन मिलेगा"),
 dict(i=6, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="सनफीस्ट बाउंस",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">2 पर ₹5 पेंसिल फ्री</span>',
   sub='सनफीस्ट बाउंस ₹5 वाला बिस्किट — 2 पैकेट खरीदने पर ₹5 वाली पेंसिल बिल्कुल फ्री; बच्चों में तेज चलने वाला आइटम · <b class="delta">₹5 पेंसिल फ्री</b>',
   l1="ऑफर", v1="₹5 वाले सनफीस्ट बाउंस के 2 पैकेट पर ₹5 वाली पेंसिल फ्री",
   l2="ग्राहक को", v2="बच्चों को बिस्किट के साथ फ्री पेंसिल; स्कूल-टाइम में तेज बिकने वाला कॉम्बो"),
 # --- News (trending_news) — in-house 11सित Pan India Schemes: मुफ्त ई-श्रम कार्ड — दुर्घटना बीमा ₹2 लाख + 60 के बाद ₹3000/माह पेंशन; concrete benefit, non-bait. Chosen over Ganesh-Chaturthi trending (overlaps गोला commodity) + QR-scam (bait). News=1 base. ---
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="ई-श्रम कार्ड",
   price='<span class="news">मुफ्त कार्ड, ₹2 लाख का बीमा</span>',
   sub='छोटे दुकानदारों के लिए मुफ्त ई-श्रम कार्ड — दुर्घटना में ₹2 लाख तक बीमा और 60 के बाद ₹3,000/माह तक पेंशन · <b class="delta">₹2 लाख बीमा</b>',
   l1="क्यों ज़रूरी", v1="16–59 साल के दुकानदार जो EPFO/ESIC में नहीं और आयकर नहीं भरते, सभी पात्र",
   l2="क्या करें", v2="eshram.gov.in पर खुद या नज़दीकी CSC पर मुफ्त बनवाएं — आधार-मोबाइल लिंक जरूरी, कोई शुल्क नहीं"),
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
