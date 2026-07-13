# KC STORIES — IMAGE PROMPT TEMPLATE (LOCKED)

> ## ⚑⚑ ARCHITECTURE CHANGE (2026-06-24) — GEMINI NO LONGER RENDERS THE CARD TEXT
> Gemini cannot render Devanagari at consistent fixed sizes — headlines drifted card-to-card and oversized until they clipped (the गुड़ bug). The fix: **Gemini now generates ONLY the photo; the whole card (masthead label, gold rule, photo, cream panel, left stripe, headline, price, sub-line, grid) is composited deterministically from a locked HTML/CSS template rendered by headless Edge + the `Nirmala UI` font** (which shapes Devanagari perfectly; PIL can't — no raqm). Script: `KC Stories/kc-card-render.py`. This makes every text element pixel-identical on every card and every day, and retires the old layout-lock / stripe-lock entirely.
>
> **The PHOTO PROMPT is now all you send to Gemini** (`generate_story_image(aspect="portrait")`): one still-life of the subject, **NO text, NO bands, NO masthead, NO panel, NO stripe** — just the photo, full frame. Subject on dark weathered wood/slate, soft daylight from upper-left, slightly desaturated wire-photo look, no people, 1–2 props. **FMCG: the real brand pack must be legible** (the brand IS the subject). **Commodity/news: generic, no brands.** The compositor crops it into the photo band (`object-fit:cover`), so exact framing is forgiving.
>
> Everything below about masthead/gold-rule/photo/panel/stripe *geometry* and the BRANDING-by-card-type table still informs the **photo** and the **template values**, but the band heights, fonts, type sizes, stripe and text are now enforced by `kc-card-render.py`, not by the prompt. Ignore the old "render the headline at 92px / draw the stripe" instructions — the template owns those.

Template for every Section 4 slide image. Narrative prose, NO doc-style labels (no "ZONE A:", no "Top section:" — just continuous description). Generated via `jack:generate_story_image(aspect="portrait")`, **then normalized by the deterministic layout-lock (see below + workflow Step 8b).**

---

## ⚑ CONSISTENCY LOCK — READ FIRST (this is why cards drifted before)

Every card MUST be visually interchangeable on scroll. Two layers enforce this:
- **Layer 1 — identical prompt scaffold.** The masthead / gold-rule / photo / cream-panel scaffold is written **byte-identical in every card's prompt**; only the photo subject and the text values change. The structural sentences below are verbatim on all 7 cards.
- **Layer 2 — post-gen layout-lock (mandatory).** Gemini does NOT honour exact pixel band heights across independent generations (masthead measured 164–222px, panel-top 50–58% even with an identical prompt). So after generating, **recomposite every card to a fixed masthead-bottom and a fixed panel-top, letting the photo absorb the slack** (recipe in `kc-stories-workflow.md` Step 8b). Devanagari cannot be re-rendered locally (no raqm shaping), so the lock only repositions/scales bands — it never re-renders text.
- **Layer 2 owns the left stripe — and the prompt must NOT draw one.** Gemini's stripe is uncontrollable (drifts in x, stops short of the bottom, doubles), and detect-and-erase clips the body text. So: the prompt **explicitly forbids any stripe/bar/line and asks for a clean empty left margin (~110/1080 px)**; then the lock **paints one uniform 14px stripe** flush to x=0, full cream-panel height, exact direction colour, with NO detection and NO cream-fill. Because the raw left band is clean cream and text starts well past 14px, the painted bar is always single, flush, full-height, and never clips text.

Bake ALL of these into every prompt, verbatim where possible:

1. **Canvas:** exactly **1080 × 1920 px**, portrait. Identical on every card.
2. **FULL-BLEED — no frame.** No outer border, no keyline, no inset margin, no rounded corners. Every band runs clean to all four edges. Do NOT draw any vertical stripe/bar/line/accent anywhere — the left edge accent is painted in the lock, not generated (rule 4).
3. **FIXED BANDS (described identically on every card).** The card is always these four stacked bands, summing to 1920:
   - Charcoal masthead — **exactly 300 px** (realistic for the large label; the old "160px" was ignored by the model and caused drift)
   - Gold rule — **exactly 4 px**
   - Editorial photograph — **exactly 760 px**
   - Cream paper panel — **fills the remaining ~856 px to the bottom edge**
   - The layout-lock (Layer 2) snaps masthead-bottom ≈ 304px-equiv and panel-top ≈ 1064px-equiv (≈55.4%) on every card after generation.
4. **THE LEFT STRIPE IS NOT DRAWN BY THE MODEL — it is painted in the lock.** The prompt must explicitly forbid any vertical stripe/bar/line/accent and request a clean empty left margin (~110/1080 px) before any text. The deterministic 14px direction-colour stripe (RED/GREEN/BLACK per the colour map) is painted onto the cream panel during the layout-lock (Step 8b-4b), flush to x=0, full panel height. Never ask Gemini to draw the stripe — its placement/length drift was the cause of edge-touch, doubling, and text-clipping bugs.
5. **HEADLINE — FIXED SIZE, NO SCALE-TO-FIT (this is what blew up the one-word "हल्दी" card).** Headline cap-height is **EXACTLY 92px** and left-aligned, the **same size on every card**. Do NOT enlarge a short one-word name to fill the width; do NOT shrink a long name — a long headline may wrap to a second line but keeps the same cap-height. Other sizes: price line 52px, sub-line/grid-values 34px, grid-labels 28px, masthead label 88px.
6. **Photo treatment identical:** subject centred on dark weathered wood / slate, soft daylight from upper-left, slightly desaturated wire-photo look, no people, hard horizontal cut at the photo's bottom edge.

If a generated card has a border, a missing stripe, a missing gold rule, or an oversized headline — regenerate; do not publish it. Then ALWAYS run the layout-lock before publishing.

---

## OPENING LINE (verbatim, every prompt)

> Create a 1080 × 1920 portrait PNG, full-bleed with NO outer border, frame, keyline, margin, or rounded corners — every section runs clean to all four edges. It is ONE card in a SET of identical-layout editorial briefing cards (Bloomberg/Economist style). The layout, band heights, fonts and type sizes are IDENTICAL on every card in the set; only the photo and the text values change. Use these EXACT fixed bands top to bottom and never vary them between cards: a 300-pixel masthead, a 4-pixel gold rule, a 760-pixel photograph, and a cream panel filling the rest to the bottom.

---

## STRUCTURE (continuous prose, top to bottom — identical scaffold on every card)

### Top charcoal masthead — exactly 300 px tall
- Deep near-black **#14181F**, full width edge to edge.
- One Devanagari section label, Mukta Bold, cap-height **88 px**, vertically centred in the band, **80 px left padding**, right side empty (no logo, no date), colour cream-white **#F2EDDF**, letter-spacing 2 px.
  - **Commodity:** "मंडी भाव" · **News:** "ट्रेंडिंग न्यूज़" · **FMCG (per segment, 2026-06-25):** "FMCG व्यापारी स्कीम" (Retailer Scheme) · "FMCG ग्राहक ऑफर" (Consumer Scheme) · "FMCG नया प्रोडक्ट लॉन्च" (new_product_launch) · "FMCG प्रोडक्ट बदलाव" (fmcg_product_change). Accent/representation per segment — see workflow Step 5 table (arrow only for प्रोडक्ट बदलाव; schemes use an offer pill, launch a नया pill).

### Gold rule — exactly 4 px, MANDATORY
- Warm metallic gold **#C8A24A**, full width edge to edge — never omit.

### Editorial photograph — exactly 760 px tall
- Edge-to-edge, hard horizontal cut at the bottom.
- Subject on **dark weathered wood or slate**, soft daylight from upper-left, slightly desaturated, no people. 1–2 context props (brass jug/katori, wooden spoon, fresh produce, condensation droplets).

**BRANDING RULES — by card type:**

| Card type | Branding rule |
|---|---|
| **Commodity** (मंडी भाव) | NO brands. Generic raw commodity — loose dal/seed heaps, plain unbranded tins, brass katoris. No packaging, no logos. |
| **FMCG** (FMCG अपडेट) | **The product's real-world branding MUST be clearly visible and legible** — the brand IS the subject. Render actual packaging as on a kirana shelf (e.g. "USHA", "Oral-B", "Godrej No.1", "Cadbury Bournvita", "Dabur Hajmola"). Real product only, no invented logos, no floating logo overlays — just the genuine pack in a still-life. |
| **News** (ट्रेंडिंग न्यूज़) | NO brands. Generic news visual — weather/monsoon scene, mandi, fields, govt building, currency, vegetables, etc. |

### Cream paper panel — fills the rest to the bottom
- Background cream **#FAFAF7**, extends to the bottom edge.
- **NO stripe in the generated image.** Tell the model to keep the extreme left edge clean empty cream and leave a generous empty left margin (~110/1080 px). The stripe is painted in the lock (Step 8b-4b) at 14px flush to x=0, full panel height, in the direction colour:
  - **RED #9A2828** for तेज़ी (price up — bad for shopkeeper)
  - **GREEN #1E7A3C** for मंदी (price down — good for shopkeeper)
  - **BLACK #1A1A1A** for FMCG and news

### Content inside cream panel
- **144 px left padding**, **80 px right padding**. Top to bottom:

  **(1) Headline** — product/commodity name. Mukta Bold, cap-height **EXACTLY 92 px**, near-black **#1A1A1A**, left-aligned. **SAME size on every card — never scale to fit; short one-word names stay this size, long names wrap to a second line at the same size.**

  **(2) Price line / sub-headline** — APPEARS EXACTLY ONCE.
  - **Commodity:** "▲"/"▼" in accent colour + "₹X" near-black + "/unit" muted grey **#7A7A7A**. Triangle+price Mukta Bold **52 px**; unit Mukta Regular **34 px**.
  - **FMCG:** "₹X → ₹Y" all Mukta Bold **52 px** near-black; the → arrow in grey #7A7A7A.
  - **News:** one-line summary, Mukta Bold **52 px** near-black.

  **(3) Sub-line** — context. Mukta Regular **34 px** grey **#7A7A7A**. Delta fragment ("₹800 बढ़ोतरी", "₹200 गिरावट", "₹840 का मार्जिन") in **Mukta Bold accent colour**.
  - **Commodity:** "पिछला भाव ₹X · ±₹Y direction · mandi · cause"
  - **FMCG:** "MRP ₹X · scheme · खरीद ₹Y · ₹Z का मार्जिन" OR "खरीद ₹X · बिक्री ₹Y · ₹Z का मार्जिन · qty"
  - **News:** "context · impact · what changes"

  **(4) Two-row grid:**
  - Left column **exactly 200 px wide**, Mukta Bold **28 px** grey **#7A7A7A**, letter-spacing 1.5, **NO COLONS**.
  - Right column Mukta Regular **34 px** near-black.
  - **1px hairline #E8E2D2** between rows.
  - **Commodity:** `क्यों` / `क्या करें` · **FMCG:** `बदलाव` / `फायदा` · **News:** `क्यों ज़रूरी` / `क्या करें`

### Bottom CTA reserve
- Bottom **220 px**: empty cream paper, no content. Reserved for the CTA overlay added at render time. (The layout-lock crops/pads here safely — never put content in this band.)

---

## LOCKED CLOSING BLOCK (verbatim at end of every prompt)

> CRITICAL — FULL-BLEED: no outer border, frame, keyline, margin or rounded corners anywhere; every section runs to all four edges. Do NOT draw any vertical stripe, bar, line or coloured accent anywhere — keep the cream panel's left edge clean empty cream (the stripe is painted afterward in the lock).
> CRITICAL — keep the fixed bands identical to the rest of the set: 300px masthead, 4px gold rule, 760px photo, cream panel to the bottom; do not resize the photo or the masthead.
> CRITICAL — the 4px gold rule is MANDATORY. Do NOT draw a left stripe; leave a clean empty left margin.
> CRITICAL — the headline is the SAME cap-height on every card; do NOT enlarge a short one-word name and do NOT shrink a long one.
> CRITICAL — DO NOT render any of these words as visible text: ZONE, MASTHEAD, PHOTO, DATA CARD, HEADLINE, PRICE BLOCK, PRICE LINE, DELTA, SUB-LINE, SUB-HEADLINE, GRID, VALUE, LABEL, ROW, COLUMN, hairline, px, pixel coordinates, hex codes, cap-height, LOCKED.
> CRITICAL — The price line appears EXACTLY ONCE on the entire card.
> No date, no KC logo, no watermark, no emoji except ▲/▼ on commodity cards, no exclamation marks, no promotional language.
> Output: a single 1080 × 1920 px PNG.

---

## DIRECTION → COLOUR QUICK MAP
| Direction | Stripe + accent | When |
|---|---|---|
| तेज़ी (price up) | RED #9A2828 | Bad for shopkeeper |
| मंदी (price down) | GREEN #1E7A3C | Good for shopkeeper |
| FMCG / news | BLACK #1A1A1A | Neutral |

---

## DATA TO EXTRACT FROM SOURCE (always include in the prompt)
- Specific numbers (₹X, ₹X → ₹Y, mandi name, weight/size).
- **FMCG: brand name AND exact product name** — must appear legibly on the pack.
- "क्यों"/"बदलाव" — factual cause. "क्या करें"/"फायदा" — operational shopkeeper guidance ("पुराने स्टॉक पर पुराना MRP बेच लें" is gold standard).

---

## FMCG PHOTO DESCRIPTION — name the brand in the prose
- ✅ "...a real USHA Shriram 9W LED retail pack, the 'USHA' wordmark and '9W LED' clearly legible on the box and bulbs..."
- ✅ "...a Cadbury Bournvita bundle of small sachets next to a pack, the 'Bournvita' wordmark clearly readable..."
- ❌ "...an unbranded jar..." / "...brand treated as natural texture..." / "...a generic pack..." (defeats the FMCG card).
