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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-08-11)
CARDS = [
 # --- Commodity (mandi_bhav) — 2 tejii/RED (सरसों तेल, बादाम) + 1 मंदी/GREEN (उड़द) for balance; all in-house ---
 dict(i=1, label="मंडी भाव", stripe=RED, headline="सरसों तेल",
   price=f'{tri("up",RED)}₹16,850<span class="unit">/क्विंटल</span>',
   sub=f'तेल मिलों की मांग निकलने और आवक घटने से सरसों तेल एक्सपेलर ₹150 चढ़कर ₹16,850/क्विंटल; सरसों दाना भी ₹100 तेज होकर ₹8,150–8,200 · <b class="delta" style="color:{RED}">+₹150/क्विंटल</b>',
   l1="क्यों", v1="तेल मिलों की मांग, स्टाकिस्टों की बिकवाली घटी; आवक 2.5 लाख से 2 लाख बोरी रह गई",
   l2="क्या करें", v2="आगे सीमित दायरे में रुख—जरूरत भर स्टॉक रखें, एकमुश्त बड़ी खरीद से बचें"),
 dict(i=2, label="मंडी भाव", stripe=GREEN, headline="उड़द",
   price=f'{tri("down",GREEN)}₹9,700<span class="unit">/क्विंटल</span>',
   sub=f'सटोरियों की बिकवाली और दाल मिलों की ठंडी ग्राहकी से उड़द SQ ₹125 टूटकर ₹9,700/क्विंटल; उड़द दाल छिलका ₹10,600–11,200 · <b class="delta" style="color:{GREEN}">−₹125/क्विंटल</b>',
   l1="क्यों", v1="दाल मिलों की ग्राहकी ठंडी और बर्मा से लगातार सस्ता आयात",
   l2="क्या करें", v2="घटे भाव पर उड़द दाल का स्टॉक भरें—आगे भाव नीचे रहने की गुंजाइश कम, बाजार दोबारा तेज लग रहा"),
 dict(i=3, label="मंडी भाव", stripe=RED, headline="बादाम",
   price=f'{tri("up",RED)}₹27,400–27,900<span class="unit">/40 किलो</span>',
   sub=f'आयातकों के पास माल कम और त्योहारी पूछपरख से बादाम कैलिफोर्निया ₹1,400 (~5.5%) उछलकर ₹27,400–27,900/40 किलो; काजू, छुहारा, पिस्ता भी तेज · <b class="delta" style="color:{RED}">+₹1,400/40 किलो</b>',
   l1="क्यों", v1="आयात कम, आयातक सस्ते में बेचने को तैयार नहीं; त्योहारी मांग शुरू",
   l2="क्या करें", v2="त्योहारी मांग तेज होने से पहले मेवा का स्टॉक भर लें, आगे और महंगा पड़ सकता है"),
 # --- FMCG (fmcg) — top 3 by Like Rate desc across ALL 4 segments after ledger dedup (news_id + 7-day brand) + body-verify. 3-category spread: home-care / pest-control / food ---
 #     Comfort fabric cond. 9.60 (product_change/रेट), Martin मच्छर मशीन 7.08 (Consumer), Priya Gold CNC 6.76 (product_change/weight) — all body-verified concrete figures.
 #     SKIPPED 7d brand (HARD): Vicks Double Power 6.55, Colgate maxfresh 6.53, Close Up Red Hot 5.86, Cadbury 5-Star 5.63.
 #     Not picked (below cut / weaker): Parle Melody 6.71, Yippee noodles 6.61, Dettol shaving 6.34 (% only, no ₹).
 dict(i=4, eyebrow="FMCG", label="प्रोडक्ट बदलाव", stripe=BLACK, headline="कंफर्ट फैब्रिक",
   price='₹58<span class="arrow">→</span>₹60<span class="unit">MRP</span>',
   sub='कंफर्ट फैब्रिक कंडीशनर (210ml) की MRP ₹58 से ₹60 हुई; दुकानदार की खरीद ₹52.2 से ₹54 (₹1.8/पीस महंगी)—अब भी करीब ₹6/पीस मार्जिन · <b class="delta">₹6/पीस मार्जिन</b>',
   l1="बदलाव", v1="MRP ₹58 → ₹60; खरीद ₹52.2 → ₹54 (₹1.8/पीस महंगा)",
   l2="फायदा", v2="पुराना स्टॉक पुराने MRP ₹58 पर बेच लें; नए माल पर भी ~₹6/पीस मार्जिन"),
 dict(i=5, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="मार्टिन मच्छर मशीन",
   price='<span class="offer" style="background:%s">मशीन के साथ साबुन फ्री</span>'%SCHEME_BLUE,
   sub='मार्टिन स्मार्ट मच्छर भगाने वाली मशीन के साथ ₹35 वाला डिटॉल साबुन बिल्कुल फ्री; मॉनसून में मच्छर की तेज़ मांग · <b class="delta">₹35 का साबुन फ्री</b>',
   l1="ऑफर", v1="हर मार्टिन मशीन के साथ ₹35 वाला डिटॉल साबुन फ्री",
   l2="ग्राहक को", v2="मशीन के दाम में ₹35 का साबुन मुफ़्त; बारिश में पक्की मांग"),
 dict(i=6, eyebrow="FMCG", label="प्रोडक्ट बदलाव", stripe=BLACK, headline="प्रिया गोल्ड CNC",
   price='<span class="wt">32g</span><span class="arrow">→</span><span class="wt">40g</span>',
   sub='प्रिया गोल्ड का ₹5 वाला CNC बिस्किट—वजन 32 ग्राम से 25% बढ़कर अब 40 ग्राम (32g+8g फ्री); उतने ही ₹5 में ज्यादा माल · <b class="delta">8g ज्यादा (25%)</b>',
   l1="बदलाव", v1="वजन 32g → 40g (₹5 में 25% यानी 8 ग्राम ज्यादा)",
   l2="फायदा", v2="उसी ₹5 में ज्यादा बिस्किट—ग्राहक को दिखाकर तेज़ बिक्री"),
 # --- News (trending_news) — खरीफ रकबा (in-house, crop/monsoon/market-impact with concrete numbers; QR-scam bait, रुझान digest & DigiDukaan/AIF non-number-lead posts SKIPPED) ---
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="खरीफ रकबा",
   price='<span class="news">बुआई 18 लाख हेक्टेयर घटी, चावल मजबूत</span>',
   sub='7 अगस्त तक खरीफ बुआई 967.92 लाख हेक्टेयर—पिछले साल से करीब 18 लाख हेक्टेयर कम; धान 2% पीछे और बारिश भी 11% कम · <b class="delta">धान 2% पीछे</b>',
   l1="क्यों ज़रूरी", v1="धान का रकबा पीछे + बारिश कम → आगे बारीक चावल के भाव मजबूत रह सकते हैं",
   l2="क्या करें", v2="चावल का जरूरी स्टॉक बनाए रखें; दलहन का अंतर घटा—दालों में ज्यादा स्टॉक की जरूरत नहीं"),
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
