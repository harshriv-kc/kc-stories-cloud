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

# ---- EDIT THIS PER DAY: 4 commodity + 4 FMCG + 1 news ----  (2026-08-30 · slide-count experiment day 2: Mandi→4 + FMCG→4)
CARDS = [
 # --- Commodity (mandi_bhav) — 2 तेजी/RED + 2 मंदी/GREEN (balance). पाम तेल / हल्दी / मखाना (in-house 30अग) + लाल मिर्च (UGC teji_mandi LR7.98, experiment 4th). ---
 dict(i=1, label="मंडी भाव", stripe=RED, headline="पाम तेल",
   price=f'{tri("up",RED)}₹12,000<span class="unit">/क्विंटल</span>',
   sub=f'कच्चा पाम तेल कांदला में ₹50 चढ़कर ₹12,000/क्विंटल; आयातकों की बिकवाली कमजोर, साबुन उद्योग की मांग निकली · <b class="delta" style="color:{RED}">₹50 तेजी</b>',
   l1="क्यों", v1="आयात करने वालों की बिकवाली कमजोर पड़ी; साबुन बनाने वालों की खरीद से एसिड ऑयल भी ₹50 चढ़ा",
   l2="क्या करें", v2="त्योहारी खपत का पाम व खाद्य तेल जरूरी माल अभी उठा लें; आगे मजबूती के आसार"),
 dict(i=2, label="मंडी भाव", stripe=GREEN, headline="हल्दी",
   price=f'{tri("down",GREEN)}₹18,500<span class="unit">/क्विंटल</span>',
   sub=f'हल्दी ईरोड गट्ठा ₹300 टूटकर ₹18,500–18,600/क्विंटल; मांग कमजोर और मुनाफावसूली से मसालों में नरमी · <b class="delta" style="color:{GREEN}">₹300 गिरावट</b>',
   l1="क्यों", v1="मांग कमजोर पड़ने और मुनाफावसूली निकलने से किराना जिंसों में नरमी आई",
   l2="क्या करें", v2="सस्ती हल्दी का त्योहारी स्टॉक अभी भर लें; भाव नीचे, आगे चढ़ने की गुंजाइश"),
 dict(i=3, label="मंडी भाव", stripe=GREEN, headline="मखाना",
   price=f'{tri("down",GREEN)}₹700–1,250<span class="unit">/किलो</span>',
   sub=f'मखाना ₹50 घटकर ₹700–1,250/किलो (क्वालिटी अनुसार); मेवा-मसालों में मुनाफावसूली, इलायची भी ₹100–150 टूटी · <b class="delta" style="color:{GREEN}">₹50 गिरावट</b>',
   l1="क्यों", v1="मेवा-मसालों में मुनाफावसूली से नरमी; ग्राहकी हल्की पड़ने पर भाव लुढ़के",
   l2="क्या करें", v2="त्योहार की जरूरत भर मखाना लें; बड़ा स्टॉक जल्दबाजी में न भरें"),
 dict(i=4, label="मंडी भाव", stripe=RED, headline="लाल मिर्च",
   price=f'{tri("up",RED)}₹250–260<span class="unit">/किलो</span>',
   sub=f'देसी सूखी साबूत लाल मिर्च 15–20 दिन में ₹230 से ₹250–260/किलो; उठाव मजबूत, आगे और तेजी के आसार · <b class="delta" style="color:{RED}">₹20–30 तेजी</b>',
   l1="क्यों", v1="बाजार में मिर्च का उठाव मजबूत और सप्लाई टाइट; आगे भी तेजी की संभावना जताई जा रही",
   l2="क्या करें", v2="त्योहारी मसाले की जरूरत की साबूत मिर्च अभी थमे भाव पर उठा लें"),
 # --- FMCG (fmcg) — TOP 4 by LR desc after ledger dedup (news_id 12d + 7d brand HARD) + body-verify. 4th slide (Rin LR4.18 >= FMCG median 1.9758) = slide-count experiment. Spread: namkeen/hygiene/health/detergent. ---
 #     haldiram LR4.44 (Retailer, ₹5 namkeen peti +1 ladi free 42+1), dettol LR4.38 (product_change, ₹91.33->₹83.03 200ml), eno LR4.31 (Retailer, 100+2 free, MRP900/740/₹160), rin LR4.18 (Consumer, 40g extra free, MRP60/46/₹14).
 #     SWAPPED: godrej-no1 LR6.45 (body only "4+1 फ्री", no ₹ figure — fails Step-6), sundar-soanpapdi LR4.41 (product_change segment but body is festive-margin pitch, no ₹X->₹Y change — segment↔body mismatch). BLOCKED 7d brand: lux, sesa, all-out, coca-cola, vim, closeup, santoor, ghadi, jolly-rancher, doms, cadbury, navratna(oil), dabur-red...
 dict(i=5, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="हल्दीराम नमकीन",
   price=f'<span class="offer" style="background:{SCHEME_GREEN}">पेटी पर 1 लड़ी फ्री</span>',
   sub='हल्दीराम ₹5 वाली नवरत्न मिक्सचर नमकीन—पूरी पेटी (42 लड़ी) लेने पर 1 लड़ी फ्री (42+1=43) · <b class="delta">1 लड़ी फ्री</b>',
   l1="स्कीम", v1="₹5 बिक्री वाली नवरत्न मिक्सचर नमकीन की पेटी पर एक लड़ी बिल्कुल फ्री",
   l2="फायदा", v2="तेज बिकने वाला ₹5 नमकीन; हर पेटी पर एक लड़ी का सीधा फायदा"),
 dict(i=6, eyebrow="FMCG", label="प्रोडक्ट बदलाव", stripe=BLACK, headline="डेटॉल लिक्विड",
   price='₹91.33<span class="arrow">→</span>₹83.03',
   sub='डेटॉल एंटीसेप्टिक लिक्विड 200ml का रेट ₹8.30 घटा—MRP ₹91.33 से ₹83.03; रोज की मांग वाला भरोसेमंद ब्रांड सस्ता · <b class="delta">₹8.30 सस्ता</b>',
   l1="बदलाव", v1="200ml डेटॉल एंटीसेप्टिक का MRP ₹91.33 से घटकर ₹83.03 हुआ",
   l2="फायदा", v2="भरोसेमंद ब्रांड सस्ता हुआ; ग्राहक की रोज मांग, तेज बिक्री"),
 dict(i=7, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="ईनो लेमन जार",
   price=f'<span class="offer" style="background:{SCHEME_GREEN}">जार पर 2 नग फ्री</span>',
   sub='ईनो फ्रूट साल्ट लेमन जार—100 सैशे पर 2 नग अंदर फ्री; कुल MRP ₹900, खरीद ₹740 · <b class="delta">₹160 मार्जिन</b>',
   l1="स्कीम", v1="लेमन ईनो जार (100 सैशे) खरीदने पर 2 नग जार के अंदर फ्री",
   l2="फायदा", v2="₹160 डायरेक्ट मार्जिन; एसिडिटी में रोज की मांग, तेज बिक्री"),
 dict(i=8, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="रिन साबुन",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">40g एक्स्ट्रा फ्री</span>',
   sub='रिन डिटर्जेंट साबुन बार—हर बार पर 40 ग्राम एक्स्ट्रा फ्री; MRP ₹60, खरीद ₹46 · <b class="delta">₹14 मार्जिन</b>',
   l1="ऑफर", v1="रिन डिटर्जेंट बार पर 40g एक्स्ट्रा साबुन बिल्कुल फ्री",
   l2="ग्राहक को", v2="वही दाम, ज्यादा साबुन; दुकानदार को ₹14 सीधा मार्जिन"),
 # --- News (trending_news) — छोटे दुकानदारों के लिए UPI मुफ्त (in-house 30अग; shopkeeper-relevant, concrete, non-bait). गांवों में खरीदारी लौटी backup (also_shown). ---
 dict(i=9, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="UPI रहेगा मुफ्त",
   price='<span class="news">छोटे दुकानदारों पर UPI शुल्क नहीं</span>',
   sub='PCI की पुष्टि—आम ग्राहक और छोटे दुकानदार UPI पहले की तरह बिल्कुल मुफ्त इस्तेमाल करेंगे; देश के डिजिटल पेमेंट में UPI का हिस्सा 85% · <b class="delta">कोई शुल्क नहीं</b>',
   l1="क्यों ज़रूरी", v1="करीब 94% छोटे दुकानदार अब UPI से पैसा ले रहे; शुल्क की अफवाहों पर विराम",
   l2="क्या करें", v2="बेझिझक डिजिटल पेमेंट लें; खुल्ले की झंझट खत्म, दिनभर का हिसाब अपने आप"),
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
