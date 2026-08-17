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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-08-17)
CARDS = [
 # --- Commodity (mandi_bhav) — no fresh in-house today (last 16 अगस्त, dedup-consumed); all MP teji_mandi. 2 तेजी/RED (मैदा, घी) + 1 मंदी/GREEN (जीरा) for balance. 3 distinct types: flour / dairy / spice-seed. ---
 #     हल्दी/लौंग/तुवर excluded (same commodity+direction as 08-16); धनिया मंदी SWAPPED OUT body-verify: no ₹ figure -> जीरा मंदी (₹270->₹260/kg concrete).
 dict(i=1, label="मंडी भाव", stripe=RED, headline="मैदा",
   price=f'{tri("up",RED)}₹22<span class="unit">/पैकेट</span>',
   sub=f'मैदा पैकेट ₹21 से ₹22 (खरीद), बिक्री ₹25 यानी ₹3 का मार्जिन; त्योहारी मांग तेज, आगे और चढ़ सकता है · <b class="delta" style="color:{RED}">+₹1/पैकेट</b>',
   l1="क्यों", v1="त्योहारों की मांग शुरू; मैदा की खपत बढ़ी, आवक पर दबाव",
   l2="क्या करें", v2="जरूरत का स्टॉक अभी बना लें; ₹3 का मार्जिन बना रहेगा"),
 dict(i=2, label="मंडी भाव", stripe=RED, headline="घी",
   price=f'{tri("up",RED)}₹200<span class="unit">/लीटर</span>',
   sub=f'हलवाई स्पेशल घी का डिब्बा ₹190 से ₹200/लीटर (+₹10); शादी-त्योहार सीजन में और तेजी की पूरी संभावना · <b class="delta" style="color:{RED}">+₹10/लीटर</b>',
   l1="क्यों", v1="शादियों-त्योहारों की मांग शुरू; घी में लगातार तेजी",
   l2="क्या करें", v2="जरूरी स्टॉक अभी उठाएं; ऊंचे भाव आगे बने रह सकते हैं"),
 dict(i=3, label="मंडी भाव", stripe=GREEN, headline="जीरा",
   price=f'{tri("down",GREEN)}₹260<span class="unit">/किलो</span>',
   sub=f'जीरा होलसेल ₹270 से ₹260/किलो पर आया (−₹10); आवक ज्यादा और मांग सुस्त, आगे और नरमी संभव · <b class="delta" style="color:{GREEN}">खरीद का मौका</b>',
   l1="क्यों", v1="मंडी में आवक बढ़ी, मांग कमजोर; मुनाफावसूली से भाव गिरे",
   l2="क्या करें", v2="भाव नीचे; त्योहारी जरूरत का माल थोड़ा-थोड़ा उठाएं"),
 # --- FMCG (fmcg) — top 3 by Like Rate desc across segments after ledger dedup (news_id 12d + 7d brand HARD) + body-verify. 3-category spread: health-drink / candy / biscuit. ---
 #     Bournvita 6.53 (product_change, MRP 295->263 clean), Silky Milky 6.20 (Retailer, Rs5 box 3 free), Parle Coconut 5.60 (product_change WEIGHT 28g->36g) — all body-verified concrete.
 #     SWAPPED OUT: soyabadi 6.35 = generic no brand pack; Nihar Amla 6.16 = packing-relaunch, only new MRPs, no clean old->new for the arrow (partial LR<->body mismatch).
 #     SKIPPED 7d brand (HARD)/news_id 12d: Lux 6.75, KitKat 6.25, Colgate 6.14/5.73/5.52/4.80, Melody 5.80/5.01, Dabur-Red 5.25, 5star 5.19, Orange-Bite 5.11, Vicks 4.93/4.46, Fevikwik 4.71; ganesh khaini 5.62 = tobacco.
 dict(i=4, eyebrow="FMCG", label="प्रोडक्ट बदलाव", stripe=BLACK, headline="बॉर्नविटा",
   price='₹295<span class="arrow">→</span>₹263<span class="unit">MRP</span>',
   sub='बॉर्नविटा 500g की MRP ₹295 से घटाकर ₹263 की गई (कंपनी ने ₹32 घटाई); ग्राहक को सीधा फायदा, बिक्री बढ़ेगी · <b class="delta">₹32 कमी</b>',
   l1="बदलाव", v1="500 ग्राम पैक की MRP ₹295 से ₹263 (₹32 की कमी)",
   l2="फायदा", v2="सस्ता होने से तेज बिकेगा; पुराना स्टॉक भी जल्दी निकालें"),
 dict(i=5, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="सिल्की मिल्की",
   price='<span class="offer" style="background:%s">बॉक्स पर 3 नग फ्री</span>'%SCHEME_GREEN,
   sub='₹5 वाली सिल्की मिल्की मिल्क चॉकलेट—एक बॉक्स लेने पर अंदर 3 नग <b class="delta">एक्स्ट्रा फ्री</b>; ₹5 पर तेज़ चलने वाला माल',
   l1="स्कीम", v1="₹5 वाली चॉकलेट का 1 बॉक्स लेने पर अंदर 3 नग फ्री",
   l2="फायदा", v2="हर बॉक्स पर 3 फ्री नग सीधा मुनाफा; बच्चों में पक्की बिक्री"),
 dict(i=6, eyebrow="FMCG", label="प्रोडक्ट बदलाव", stripe=BLACK, headline="पारले कोकोनट",
   price='28g<span class="arrow">→</span>36g<span class="unit">वजन</span>',
   sub='पारले कोकोनट बिस्कुट का वजन 28g से 36g हुआ (28% ज्यादा), पैक वही ₹40 में 12 पीस; दुकानदार को ₹20 का मार्जिन · <b class="delta">वजन +28%</b>',
   l1="बदलाव", v1="पैक का वजन 28 ग्राम से 36 ग्राम (28% ज्यादा)",
   l2="फायदा", v2="ज्यादा वजन पर वही ₹40 दाम; ₹20 मार्जिन, ग्राहक खुश"),
 # --- News (trending_news) — खुदरा महंगाई 19 महीने के उच्चतम पर (MP news LR 3.68; market-impact + concrete + actionable). दाल-स्टॉक (LR 2.95) considered; लाइसेंस-सीमा = 07-06 FSSAI topic repeat, skipped. ---
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="महंगाई बढ़ी",
   price='<span class="news">खुदरा महंगाई 4.45%, 19 महीने में सबसे ऊंची</span>',
   sub='जुलाई में खुदरा महंगाई 4.45% (जून 4.38%); खाद्य महंगाई 5.52%, गांवों पर बोझ ज्यादा; थोक लागत बढ़ेगी · <b class="delta">19 महीने का उच्चतम</b>',
   l1="क्यों ज़रूरी", v1="थोक भाव चढ़ेंगे; कंपनियां पैक का वजन घटा सकती हैं",
   l2="क्या करें", v2="रोज़ भाव पर्ची बनाएं; थोक बढ़ते ही भाव ठीक करें, उधार सख्त रखें"),
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
