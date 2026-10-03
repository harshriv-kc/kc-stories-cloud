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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-10-03 . experiment window CLOSED -> base 3+3+1)
CARDS = [
 # Commodity (mandi_bhav) - 2 teji/RED (kabuli chana in-house daal, jau in-house Samachar) + 1 mandi/GREEN (anjeer in-house mewa). Direction balance 2R+1G. 3 DISTINCT in-house posts -> 3 distinct news_ids. arhar/sarson/binola/soyabean skipped (same commodity+dir within 3d). rujhan digest skipped. MP teji_mandi rows are outlook-only (no concrete Rs) -> not usable for a priced card.
 dict(i=1, label="मंडी भाव", stripe=RED, headline="काबुली चना",
   price=f'{tri("up",RED)}₹8,500<span class="unit">/क्विंटल</span>',
   sub=f'काबुली चना +₹300 → महाराष्ट्र ₹8,300–8,500/क्विंटल; सिर्फ 10 दिन में ₹13/किलो उछला, दिल्ली मोटा दाना ₹11,700–12,000 · <b class="delta" style="color:{RED}">₹300 तेजी</b>',
   l1="क्यों", v1="पुराना स्टॉक निपट गया और हाजिर में माल की कमी; MP की नई फसल के लिए खेतों की नमी ठीक नहीं, विदेश में भी भाव ऊंचे",
   l2="क्या करें", v2="त्योहारी मांग से पहले जरूरत भर का माल उठा लें; पुराना-नया स्टॉक अलग रखकर रेट बताएं, ~4% और तेजी के आसार"),
 dict(i=2, label="मंडी भाव", stripe=GREEN, headline="अंजीर",
   price=f'{tri("down",GREEN)}₹800<span class="unit">/किलो</span>',
   sub=f'अंजीर मंदी → थोक बढ़िया ₹800/किलो, नीचे का ₹500–550; 40 किलो सामान्य ₹21,800–23,500, नई फसल के साथ पुराना स्टॉक भारी · <b class="delta" style="color:{GREEN}">भाव दबे</b>',
   l1="क्यों", v1="डेढ़ महीने से नई फसल लगातार आ रही और पुराना माल ज्यादा; अफगानिस्तान का सस्ता माल, उत्पादन +8–10%, दो साल का स्टॉक जमा",
   l2="क्या करें", v2="मिठाई-गिफ्ट पैक की मांग के लिए सस्ते भाव पर जरूरत भर उठाएं; लंबा स्टॉक न लगाएं, भाव बढ़ने के आसार कम"),
 dict(i=3, label="मंडी भाव", stripe=RED, headline="जौ",
   price=f'{tri("up",RED)}₹2,950<span class="unit">/क्विंटल</span>',
   sub=f'जौ +₹60–90 → ₹2,900–2,950/क्विंटल; माल्ट व फ्लोर मिलों की खरीद निकली और उत्पादन घटा, जल्द ₹3,000 पार के आसार · <b class="delta" style="color:{RED}">₹90 तक तेजी</b>',
   l1="क्यों", v1="बुवाई का रकबा घटकर करीब 4 लाख हेक्टेयर रह गया; प्रोटीन व माल्ट कंपनियों की खरीद तेज, हाजिर माल कम",
   l2="क्या करें", v2="जौ व सत्तू का जरूरत भर माल अभी रख लें; नई फसल आने तक भाव ₹3,000 पार जा सकते हैं"),
 # FMCG (fmcg) - TOP 3 by LR desc across segments after ledger dedup (news_id 12d + brand 7d incl also_shown) + body-verify (all concrete Rs). Category spread: candy / detergent / dishwash.
 #   snakker LR7.92 Retailer (peti MRP135, 30 nag x Rs5 = Rs150, Rs15 margin), surf-excel LR6.08 Consumer (1kg bag -> 2 Rs10 pouches free, buy 128.33 vs MRP147), exo LR5.97 Consumer (Rs5 -> 50g+40g extra = 90g).
 #   BLOCKED brand7d (incl also_shown): santoor/sensodyne/param-ghee/colgate/gillette/margo/hajmola/alpenliebe/nima/patanjali-dant-kanti/lux/vim/ghadi/my-fruit-jelly/pulse/dabur-amla/priyagold-tomtom/kesh-king/dettol/good-knight/tide. Vague no-number MP rows dropped.
 dict(i=4, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="स्नैकर चॉकलेट",
   price=f'<span class="offer" style="background:{SCHEME_GREEN}">पेटी ₹135 · ₹15 मुनाफ़ा</span>',
   sub='स्नैकर चॉकलेट की पेटी (खरीद MRP ₹135) में 30 नग; हर नग ₹5 में बिक्री → कुल ₹150, एक पेटी पर सीधा ₹15 का मुनाफ़ा · <b class="delta">₹15/पेटी मुनाफ़ा</b>',
   l1="स्कीम", v1="एक पेटी = 30 नग, दुकानदार की खरीद MRP ₹135 में",
   l2="फायदा", v2="हर नग ₹5 → ₹150 कुल बिक्री, ₹15 सीधा मुनाफ़ा प्रति पेटी"),
 dict(i=5, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="सर्फ एक्सेल",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">1kg पर 2 पाउच फ्री</span>',
   sub='सर्फ एक्सेल 1kg बोरी (12 पैकेट, ₹1,540) — हर 1kg के साथ ₹10 वाले 2 पाउच ग्राहक को फ्री; दुकानदार की खरीद ₹128.33 vs MRP ₹147 · <b class="delta">₹20 का माल फ्री</b>',
   l1="ऑफर", v1="1kg सर्फ एक्सेल के साथ ₹10 वाले 2 पाउच बिल्कुल फ्री",
   l2="ग्राहक को", v2="₹20 का माल मुफ्त; स्कीम से बिक्री तेज, दुकानदार को भी मार्जिन"),
 dict(i=6, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="एक्सो बार",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">₹5 में 90g (40g एक्स्ट्रा)</span>',
   sub='एक्सो बर्तन धोने का बार सिर्फ ₹5 में — 50g के साथ 40g एक्स्ट्रा, कुल 90g; वही ₹5 दाम पर लगभग दोगुना माल · <b class="delta">40g एक्स्ट्रा फ्री</b>',
   l1="ऑफर", v1="₹5 में 50g + 40g एक्स्ट्रा = कुल 90g का बार",
   l2="ग्राहक को", v2="वही ₹5 दाम, लगभग दोगुना साबुन — रोज़ की जरूरत पर सीधी बचत"),
 # News (trending_news) - in-house 3oct Pan India Trending 1: new UPI MDR rule from 15 Oct, small shops (<=Rs1 lakh/month) zero charge. Non-bait, concrete figures, universal dukandar relevance + clears active confusion. News=1 base. (chini stock-limit + swamitva scheme kept as backups; nakli-ghee bait never considered.)
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="UPI नया नियम",
   price='<span class="news">छोटी दुकानों पर UPI शुल्क नहीं</span>',
   sub='15 अक्टूबर से UPI पर नया MDR नियम — ₹2,000 तक हर पेमेंट फ्री; महीने में ₹1 लाख तक वसूली वाली दुकानों पर किसी भी रकम पर शून्य शुल्क · <b class="delta">₹1 लाख तक शून्य शुल्क</b>',
   l1="क्यों ज़रूरी", v1="देश की ज्यादातर किराना दुकानें ₹1 लाख/माह के दायरे में — उन पर एक पैसा शुल्क नहीं, GST भी जरूरी नहीं",
   l2="क्या करें", v2="अपनी महीने भर की UPI वसूली जोड़कर देखें; ग्राहक से यह शुल्क वसूलना मना, उसके लिए UPI मुफ्त ही रहेगा"),
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
