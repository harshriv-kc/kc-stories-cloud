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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-08-20)
CARDS = [
 # --- Commodity (mandi_bhav) — 2 तेजी/RED + 1 मंदी/GREEN(मखाना) for balance. Types: pulse / foxnut / dry-coconut. देसी चना + मखाना in-house (20अग), नारियल MP teji_mandi LR7.31 (body-verified ₹37,500). ---
 dict(i=1, label="मंडी भाव", stripe=RED, headline="देसी चना",
   price=f'{tri("up",RED)}₹6,475<span class="unit">/क्विंटल</span>',
   sub=f'देसी चना ₹6,275 से ₹6,475/क्विंटल (महीने भर में +₹200); आपूर्ति चौतरफा घटी, ऑस्ट्रेलियाई आयात महंगा—चना दाल-बेसन भी चढ़े · <b class="delta" style="color:{RED}">₹200 तेजी</b>',
   l1="क्यों", v1="घरेलू उत्पादन ~90 लाख टन बनाम खपत ~140 लाख टन; माल घटा, आयात महंगा",
   l2="क्या करें", v2="चना दाल-बेसन जरूरत भर अभी उठा लें; भाव ₹7,000 तक जाने के आसार, नई फसल दूर"),
 dict(i=2, label="मंडी भाव", stripe=GREEN, headline="मखाना",
   price=f'{tri("down",GREEN)}₹1,300<span class="unit">/किलो</span>',
   sub=f'मखाना ₹1,350 से ₹1,300/किलो पर नरम (−₹50); उठाव कमजोर, बाजार रेंज ₹750–1,300/किलो · <b class="delta" style="color:{GREEN}">₹50 गिरावट</b>',
   l1="क्यों", v1="उठाव और मांग सुस्त रहने से भाव मुलायम पड़े",
   l2="क्या करें", v2="नरमी में स्टॉक थोड़ा रुककर भरें; व्रत-त्योहार मांग पर फिर तेजी संभव"),
 dict(i=3, label="मंडी भाव", stripe=RED, headline="सूखा नारियल",
   price=f'{tri("up",RED)}₹37,500<span class="unit">/क्विंटल</span>',
   sub=f'गोला कट्टा ₹37,500/क्विंटल पर मजबूत; सावन व्रत-त्योहार की मांग और दक्षिण मंडियों में आवक कमजोर · <b class="delta" style="color:{RED}">भाव तेज</b>',
   l1="क्यों", v1="व्रत-त्योहार की मांग तेज और दक्षिण भारत से आवक कमजोर",
   l2="क्या करें", v2="पूजा-त्योहार की खपत से पहले जरूरी माल उठा लें, भाव मजबूत रहेंगे"),
 # --- FMCG (fmcg) — top by Like Rate desc after ledger dedup (news_id 12d + 7d brand HARD) + body-verify. 3-category spread: stationery / biscuit / hair-dye. ---
 #     natraj-pencil Retailer 6.37 (Rs35 box, 10 pencil + eraser + cutter, Rs25 margin), parle-g Consumer 5.43 (Rs5 MRP, 10+2 free), vasmol Consumer 3.44 (buy Rs50 sell Rs65 = Rs15 margin + free paste) — all body-verified concrete.
 #     SWAPPED OUT: hajmola 7.89 = body has NO rupee figure (only "10pcs free" free-goods, no price/margin) -> Step-6 no-number reject; parle-mazelo 5.09 = would be a 2nd Parle card same day (brand monotony), kept single Parle=parle-g; patanjali-toothpaste 3.54 = 3rd-consecutive-day oral-care (colgate 18अग, oral-b 19अग) -> soft category-spread. SKIPPED 7d brand/news_id: colgate 5.27, center-fruit 5.85, jasmine-mehndi 5.71, kurkure 5.58, bournvita 5.49, parle-coconut 5.40, tim-buk-tu 4.77, lux 4.41, chik 4.05, silky-milky 3.98, sabke-sai-dhoop 3.31, kitkat 3.22; KP-group 3.15 = pan masala; golden-dairy-cream 4.11 & haldiram 3.86 = no rupee figure.
 dict(i=4, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="नटराज पेंसिल",
   price='<span class="offer" style="background:%s">बॉक्स में रबर+कटर फ्री</span>'%SCHEME_GREEN,
   sub='₹35 थोक का नटराज बोल्ड बॉक्स—अंदर 10 पेंसिल के साथ 1 रबर और 1 कटर फ्री; हर पेंसिल ₹5 बिक्री · <b class="delta">₹25 मुनाफा/बॉक्स</b>',
   l1="स्कीम", v1="₹35 के बॉक्स में 10 पेंसिल के साथ एक रबर और एक कटर फ्री",
   l2="फायदा", v2="पेंसिल पर ₹15 + रबर ₹5 + कटर ₹5 = हर बॉक्स पर ₹25 मुनाफा"),
 dict(i=5, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="पारले-जी",
   price='<span class="offer" style="background:%s">10 पर 2 पैकेट फ्री</span>'%SCHEME_BLUE,
   sub='₹5 वाला पारले-जी बिस्कुट—10 पैकेट खरीद पर 2 पैकेट फ्री (10+2); रोज बिकने वाली, ग्राहक खींचने वाली स्कीम · <b class="delta">MRP ₹5</b>',
   l1="ऑफर", v1="₹5 MRP के 10 पैकेट पर 2 पैकेट बिल्कुल फ्री",
   l2="ग्राहक को", v2="हर 10 पैकेट पर 2 अतिरिक्त—तेज खपत वाला भरोसेमंद बिस्कुट"),
 dict(i=6, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="वासमोल डाई",
   price='<span class="offer" style="background:%s">डाई पर पेस्ट फ्री</span>'%SCHEME_BLUE,
   sub='वासमोल केश काला छोटी डाई—खरीद ₹50, बिक्री ₹65; हर पैक के साथ एक हेयर पेस्ट बिल्कुल फ्री · <b class="delta">₹15 मार्जिन</b>',
   l1="ऑफर", v1="छोटी डाई के साथ एक हेयर डाई पेस्ट बिल्कुल फ्री",
   l2="ग्राहक को", v2="₹65 में डाई और फ्री पेस्ट; दुकानदार को ₹15 का मार्जिन"),
 # --- News (trending_news) — चीनी import-duty relief (in-house 20अग; market-impact, actionable, non-bait). Sugar heavily covered 18-19अग as commodity but this is a fresh policy angle (import to cool record prices). ---
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="चीनी आयात",
   price='<span class="news">सरकार 10 लाख टन आयात छूट पर विचार</span>',
   sub='चीनी दिल्ली हाजिर ₹6,100–6,200/क्विंटल के रिकॉर्ड पर; 100% आयात टैक्स घटाकर अक्टूबर तक 10 लाख टन मंगाने की छूट पर विचार · <b class="delta">भाव नरम पड़ सकते</b>',
   l1="क्यों ज़रूरी", v1="माल की तंगी और त्योहारी मांग से रिकॉर्ड भाव; आयात खुलते ही नरमी आ सकती है",
   l2="क्या करें", v2="रिकॉर्ड भाव पर महीनों का बड़ा स्टॉक न भरें; त्योहारी बिक्री भर का माल लें"),
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
