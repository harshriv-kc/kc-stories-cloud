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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-08-03)
CARDS = [
 # --- Commodity (mandi_bhav) — 1 तेजी/RED (छोटी इलायची, in-house) + 2 मंदी/GREEN (उड़द, सोया तेल, in-house) for balance;
 #     yesterday's सरसों तेल/मूंग/गेहूं all avoided (7-day commodity freshness) ---
 dict(i=1, label="मंडी भाव", stripe=RED, headline="छोटी इलायची",
   price=f'{tri("up",RED)}₹3,650<span class="unit">/किलो</span>',
   sub=f'छोटी इलायची ₹100 चढ़कर ₹3,650/किलो के ऊंचे स्तर पर; औसत भाव ₹3,150; नीलामी में 75,108 किलो आवक पर भी खरीदार डटे रहे · <b class="delta" style="color:{RED}">+₹100/किलो</b>',
   l1="क्यों", v1="लगातार ग्राहकी और बिकवाली का दबाव कम; सावन बाद रक्षाबंधन-त्योहारों की मिठाई-हलवाई मांग बढ़ेगी",
   l2="क्या करें", v2="महंगी जिंस है, पूरी पूंजी दब जाती है—आधा माल अभी और आधा दो हफ्ते बाद लें; छोटे पैकेट में बेचें"),
 dict(i=2, label="मंडी भाव", stripe=GREEN, headline="उड़द",
   price=f'{tri("down",GREEN)}₹9,300<span class="unit">/क्विंटल</span>',
   sub=f'दिल्ली उड़द FAQ ₹25 घटकर ₹9,300/क्विंटल; SQ ₹9,800–9,825, चेन्नई FAQ ₹9,150; दाल मिलों की ग्राहकी सुस्त · <b class="delta" style="color:{GREEN}">−₹25/क्विंटल</b>',
   l1="क्यों", v1="चेन्नई के सौदे निपट गए और आयातकों की मुनाफावसूली से बिकवाली का दबाव; बर्मा का माल भी नरम",
   l2="क्या करें", v2="यह हल्की गिरावट खरीद का मौका—त्योहारी उड़द दाल, मोगर और पापड़-बड़ी का माल थोड़ा-थोड़ा उठाकर औसत नीचे रखें"),
 dict(i=3, label="मंडी भाव", stripe=GREEN, headline="सोया तेल",
   price=f'{tri("down",GREEN)}₹15,500<span class="unit">/क्विंटल</span>',
   sub=f'दिल्ली सोया रिफाइंड ₹100 घटकर ₹15,500/क्विंटल; कांदला ₹14,400, देवास ₹14,600; विदेशी बाजार नरम और मंडियों में उठाव कमजोर · <b class="delta" style="color:{GREEN}">−₹100/क्विंटल</b>',
   l1="क्यों", v1="विदेशी बाजार नरम और मध्य प्रदेश–महाराष्ट्र की मंडियों में सोया तेल का उठाव नहीं निकला",
   l2="क्या करें", v2="भाव सीमित दायरे में रहेंगे—एक साथ भारी माल न भरें, जरूरत भर का ही लें, पैसा फंसाने से बचें"),
 # --- FMCG (fmcg) — top 3 by Like Rate desc across ALL 4 segments after ledger dedup (news_id + 7-day brand) + body-verify ---
 #     Sensodyne 5.88 (Retailer), Cadbury 5 Star 5.84 (Retailer), Parachute Protein Shampoo 5.11 (नया लॉन्च). oral-care + chocolate + hair-care for category spread.
 #     REJECTED no-number (body-verify): Tata Soulful Wafers 6.90 ("1+1" only, no ₹). SKIPPED brand-dup(7d): Hajmola 7.95, Parle 7.85, Colgate 7.77/6.78/6.11, 7-Star 6.97, Jasmine 6.89, Closeup 6.82, Navratna 6.66, Mantos 6.58, Oral-B 6.40, Derby 6.29, Ankit 6.12, Alpenliebe 6.09, Just Jelly 5.62, Nirma 5.90. Tom Tom 5.50 skipped (thin body + chocolate overlap).
 dict(i=4, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="सेंसोडाइन टूथब्रश",
   price='<span class="offer" style="background:%s">पत्ते पर 2 ब्रश फ्री</span>'%SCHEME_GREEN,
   sub='₹31 MRP वाले सेंसोडाइन ब्रश के पूरे पत्ते की खरीद ₹240, बिक्री ₹420; साथ में ₹62 MRP के 2 ब्रश फ्री · <b class="delta">₹180 मार्जिन</b>',
   l1="स्कीम", v1="₹240 में पूरा पत्ता, बिक्री ₹420; ऊपर से ₹62 MRP के 2 ब्रश बिल्कुल फ्री",
   l2="फायदा", v2="पूरा पत्ता बिकने पर ₹180 का सीधा मार्जिन; ब्रश की क्वालिटी अच्छी, तेज़ बिकने वाला माल"),
 dict(i=5, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="कैडबरी 5 स्टार",
   price='<span class="offer" style="background:%s">39 पीस पर 1 फ्री</span>'%SCHEME_GREEN,
   sub='₹10 वाली 5 स्टार चॉकलेट का बॉक्स (39+1 पीस) होलसेल ₹372, बिक्री ₹400; हर पीस ₹10 · <b class="delta">₹28 मार्जिन</b>',
   l1="स्कीम", v1="₹372 के बॉक्स में 39 पीस के साथ 1 पीस फ्री, हर पीस ₹10 बिक्री",
   l2="फायदा", v2="पूरा बॉक्स ₹400 में बिकने पर ₹28 का मार्जिन; ₹10 प्राइस पॉइंट पर तेज़ बिकने वाली चॉकलेट"),
 dict(i=6, eyebrow="FMCG", label="नया प्रोडक्ट लॉन्च", stripe=LAUNCH_AMBER, headline="पैराशूट प्रोटीन शैंपू",
   price='<span class="newtag" style="background:%s">नया</span><span class="mrp">MRP ₹55</span>'%LAUNCH_AMBER,
   sub='पैराशूट का नया प्रोटीन शैंपू (80g) MRP ₹55, होलसेल ₹45; हर बोतल पर सीधा ₹10 का मार्जिन · <b class="delta">₹10 मार्जिन</b>',
   l1="नया क्या", v1="कंपनी ने 80g वाला नया पैराशूट प्रोटीन शैंपू ₹55 MRP पर उतारा, होलसेल ₹45",
   l2="फायदा", v2="हर बोतल पर सीधा ₹10 मार्जिन; प्रोटीन शैंपू की नई मांग, छोटे पैक से तेज़ बिक्री"),
 # --- News (trending_news) — अगस्त में कम बारिश का अनुमान (मौसम विभाग/अल नीनो), दाल-तेल भाव पर असर (in-house, monsoon/crop market-impact, non-bait) ---
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="कम बारिश अलर्ट",
   price='<span class="news">अगस्त में कम बारिश—दाल-तेल भाव मजबूत रह सकते हैं</span>',
   sub='मौसम विभाग का अनुमान—अगस्त में औसत का 94% से कम बारिश; प्रशांत में अल नीनो का असर · <b class="delta">42% जिले सूखे</b>',
   l1="क्यों ज़रूरी", v1="कम बारिश से दाल, तिलहन, चावल की फसल दबेगी; आगे भाव मजबूत रह सकते हैं",
   l2="क्या करें", v2="सबसे ज्यादा बिकने वाली दाल और खाने का तेल आज के भाव पर थोड़ा भर लें"),
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
