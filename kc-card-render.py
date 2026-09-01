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

# ---- EDIT THIS PER DAY: 4 commodity + 4 FMCG + 1 news ----  (2026-08-31 · slide-count experiment day 3: Mandi->4 + FMCG->4, News=1)
CARDS = [
 # --- Commodity (mandi_bhav) — 3 तेजी/RED + 1 मंदी/GREEN. In-house 1सित: राइस ब्रान (तेल बाजार तेजी) + राजमा (दाल बाजार मंदी) + गोला बुरादा (मेवा तेजी) + किशमिश (UGC teji_mandi LR6.88, experiment 4th). ---
 dict(i=1, label="मंडी भाव", stripe=RED, headline="राइस ब्रान तेल",
   price=f'{tri("up",RED)}₹13,700<span class="unit">/क्विंटल</span>',
   sub=f'राइस ब्रान ऑयल ₹200 उछलकर ₹13,700/क्विंटल; रिफाइंड-ब्लेंडिंग मांग निकली और आपूर्ति घटी · <b class="delta" style="color:{RED}">₹200 तेजी</b>',
   l1="क्यों", v1="रिफाइंड और ब्लेंडिंग वालों की मांग निकली, आपूर्ति घटी; बिनौला-पाम तेल भी मजबूत",
   l2="क्या करें", v2="जरूरत का माल भर लें; गिरावट की गुंजाइश कम, बाजार मजबूत रह सकता है"),
 dict(i=2, label="मंडी भाव", stripe=GREEN, headline="राजमा चित्रा",
   price=f'{tri("down",GREEN)}₹9,800<span class="unit">/क्विंटल</span>',
   sub=f'राजमा चित्रा ₹400–500 टूटकर ₹9,800–10,200/क्विंटल; स्टॉकिस्टों की बिकवाली और नई फसल का दबाव · <b class="delta" style="color:{GREEN}">₹500 गिरावट</b>',
   l1="क्यों", v1="बड़े स्टॉकिस्टों की बिकवाली भारी; बारसी में करीब 6 लाख बोरी नई फसल की खबर",
   l2="क्या करें", v2="यह भरने का भाव है, बेचने का नहीं; एक-डेढ़ महीने का साफ दाना अभी तौल लें"),
 dict(i=3, label="मंडी भाव", stripe=RED, headline="गोला बुरादा",
   price=f'{tri("up",RED)}₹7,300<span class="unit">/25 किलो</span>',
   sub=f'गोला बुरादा सामान्य ₹7,300 और बढ़िया ₹7,500 प्रति 25 किलो पर मजबूत; त्योहारी हलवाई मांग तेज · <b class="delta" style="color:{RED}">₹100 तेजी</b>',
   l1="क्यों", v1="गणेश उत्सव और आगे के त्योहारों की मिठाई-प्रसाद मांग; दक्षिण से आवक सीमित",
   l2="क्या करें", v2="अभी ₹7,300 पर भर लें; सूखी जगह बंद डिब्बे में रखें, छोटे पैकेट बनाकर बेचें"),
 dict(i=4, label="मंडी भाव", stripe=RED, headline="किशमिश",
   price=f'{tri("up",RED)}₹520<span class="unit">/किलो</span>',
   sub=f'किशमिश ₹400 से चढ़कर ₹520/किलो; त्योहार आते ही मांग तेज, ₹120 की तेजी · <b class="delta" style="color:{RED}">₹120 तेजी</b>',
   l1="क्यों", v1="त्योहारी मांग निकलते ही किशमिश के दाम तेज; आगे और तेजी के आसार",
   l2="क्या करें", v2="त्योहार से पहले जरूरी स्टॉक भर लें; मांग बढ़ने पर भाव और चढ़ सकते हैं"),
 # --- FMCG (fmcg) — TOP 4 by LR desc after ledger dedup (news_id 12d + brand 7d) + body-verify; all Consumer Scheme (ग्राहक ऑफर). 4th slide (Dabur Vatika LR3.877 >= FMCG median 2.475) = slide-count experiment. ---
 #     parachute LR6.43 (190ML+45ML free), whisper LR4.17 (33+3), nycil LR3.94 (150g+50g free), dabur-vatika LR3.88 (shampoo+free almond oil, MRP190/WS142/margin48).
 #     BLOCKED 7d brand: lux, cadbury, eno, vim, sesa, xpert, ponds, coca-cola, patanjali-dant-kanti, all-out, britannia, dettol, kurkure.
 dict(i=5, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="पैरासूट जस्मीन",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">190ML पर 45ML फ्री</span>',
   sub='पैरासूट एडवांस्ड जस्मीन विथ विटामिन-E 190ML पर 45ML बिल्कुल फ्री; उसी दाम में करीब एक-चौथाई तेल ज्यादा · <b class="delta">45ML फ्री</b>',
   l1="ऑफर", v1="190ML पैरासूट एडवांस्ड जस्मीन तेल पर 45ML बिल्कुल फ्री",
   l2="ग्राहक को", v2="उसी दाम में करीब 24% ज्यादा तेल; तेज बिकने वाला हेयर ऑयल"),
 dict(i=6, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="व्हिस्पर चॉइस XL",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">33 पर 3 फ्री</span>',
   sub='व्हिस्पर चॉइस XL सैनिटरी पैड पर 33+3 की स्कीम—33 पैड पर 3 पैड बिल्कुल फ्री · <b class="delta">3 पैड फ्री</b>',
   l1="ऑफर", v1="व्हिस्पर चॉइस XL पैड पर 33 खरीदने पर 3 नग फ्री (33+3)",
   l2="ग्राहक को", v2="रोज़ काम आने वाला प्रोडक्ट; हर 33 पर 3 पैड का सीधा फायदा"),
 dict(i=7, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="नायसिल पावडर",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">150g पर 50g फ्री</span>',
   sub='नायसिल जर्म एक्सपर्ट 150 ग्राम खरीदने पर 50 ग्राम बिल्कुल फ्री; बरसात-उमस में तेज बिक्री · <b class="delta">50g फ्री</b>',
   l1="ऑफर", v1="150 ग्राम नायसिल जर्म एक्सपर्ट पावडर पर 50 ग्राम फ्री",
   l2="ग्राहक को", v2="उसी दाम में एक-तिहाई पावडर ज्यादा; मौसमी मांग तेज"),
 dict(i=8, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="वाटिका शैम्पू",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">बादाम तेल फ्री</span>',
   sub='डाबर वाटिका हेल्थ शैम्पू पर ₹33 का डाबर बादाम हेयर ऑयल 45ML अंदर फ्री; MRP ₹190, खरीद ₹142 · <b class="delta">₹48 मार्जिन</b>',
   l1="ऑफर", v1="वाटिका शैम्पू बोतल पर डाबर बादाम तेल 45ML (₹33) अंदर फ्री",
   l2="ग्राहक को", v2="ग्राहक को ₹33 का बादाम तेल मुफ्त; दुकानदार को ₹48 सीधा मार्जिन"),
 # --- News (trending_news) — in-house 1सित Trending News 1: दूध थोक ₹93->102/लीटर (+9), concrete market-impact, non-bait. News stays 1 per experiment protocol. ---
 dict(i=9, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="दूध ₹9 महंगा",
   price='<span class="news">थोक ₹93 → ₹102/लीटर</span>',
   sub='मुंबई दूध संघ ने थोक दूध ₹93 से ₹102/लीटर किया (~10%); खुदरा ₹110–112 तक जा सकता है · <b class="delta">₹9 बढ़ोतरी</b>',
   l1="क्यों ज़रूरी", v1="चारा-पशु लागत बढ़ी, कच्चे दूध की आपूर्ति घटी; दही-पनीर-मिठाई सब महंगे होंगे",
   l2="क्या करें", v2="घी-दूध पाउडर आज के भाव पर भर लें; रोज़ के दूध-दही पर मुनाफा धीरे-धीरे बढ़ाएं"),
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
