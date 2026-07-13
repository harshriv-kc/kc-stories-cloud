# KC STORIES — CIRCULAR BADGE TEMPLATE (LOCKED)

Template for every Section 5 entry badge. Narrative prose, ~350 words. Three badges per day — one per category (commodity, FMCG, news), each picking the strongest visual hook from that day's picks. Generated via `jack:generate_story_image(aspect="square")`, **then normalized by the deterministic ring composite (below)**, then pushed with `jack:update_story_entry_badges`.

---

## ⚑ CONSISTENCY LOCK — READ FIRST

All three badges must look like one set:
1. **Canvas:** square **1:1**, pure white background **#FFFFFF** outside the circle (no border, no frame).
2. **Ring — FLAT SOLID, THIN, IDENTICAL.** The outer ring is a **flat solid single colour** (NO gradient), **uniform brick-red #B92B0F**, of **uniform thickness ≈ 4.5% of the badge diameter**, the same width at every point around the circle AND identical across all three badges. **RED sits FLUSH to the badge's outer edge — there is NO white ring outside the red.** A white **inner separator ring** sits between the photo/content and the red, **≈ 3.2% of the diameter** (bumped from 1.5% on 2026-07-10 so it reads as a clear ring: content → white ring → red-at-edge, like the reference जीरा badge). ⚑ **In the transparent PN export the inner white ring is cut to TRANSPARENT** (mask = content disc + red annulus opaque, the white ring between them transparent), so the PN reads photo + transparent gap + red-at-edge and the push background shows through the gap. `kc-badge-banner.py` owns all of this deterministically (`sep_w=0.032·D`, red drawn flush at the canvas edge growing inward, PN compound mask). State this verbatim in every badge prompt. **Why flat + thin:** a gradient ring drifts in orientation/saturation across independent generations, and prompted thickness was measured varying 6–9% card-to-card. Flat solid kills the colour drift; the post-gen composite (below) kills the thickness/size drift. **Do not go back to a gradient or an 8% ring.**
3. **Identical bottom banner:** dark curved banner of the **same height (~40% of the circle)** on all three, with the same golden trim line, carrying the same **VERY LARGE / oversized** yellow headline that fills almost the whole banner.
4. **One subject + one tag + 1–2 props.** No clutter, no people, no logos, no brand labels (badges are generic even for FMCG — branding lives on the slide card, not the badge).

---

## ⚑ MANDATORY POST-GENERATION NORMALIZE (this is what actually guarantees uniformity)

Prompting alone cannot pin ring thickness or circle size across three independent generations (measured drifting 6.2% / 9.0% / 8.1% even with an identical prompt). So after generating the 3 square badges, **always run the deterministic ring composite before uploading** (full recipe in `kc-stories-workflow.md` Step 9b). Per badge:
1. `curl` the generated `.webp` to a local file.
2. Detect the badge circle's bounding box → centre + radius.
3. Crop the **interior at ~90% radius** (drops the model's own thin ring + separator, which occupy only the outer ~10% of the radius), rescale that interior to a **common diameter** (so all three circles are the same size). ⚠ **90%, not 80%** — since the 2026-07-06 bigger-banner-text rule the oversized headline reaches past 80%r, so an 80% crop clips the bottom banner line; 90% keeps all banner text while still dropping the model's ring.
4. Redraw an **identical flat ring**: red band = **4.5% of diameter**, white separator = **1.5%**, perfectly concentric, on every badge.
5. Re-upload the composited PNG via `jack:upload_image(blob="news")` and use THAT url in `update_story_entry_badges`.

Result: the three rings are pixel-identical regardless of what Gemini produced.

## ⚑⚑ CURRENT BADGE DESIGN (2026-07-09 — CURVED BANNER + CLICKY copy) — SUPERSEDES the gradient look below

Operator reverted the gradient-overlay ("Option D") on 2026-07-09: *"image and text separate like before is g2g — text >50%, curved separator NOT a straight line; copy not clicky enough."* The current live design (baked into `kc-badge-banner.py`):
- **Image on top (~48%) + dark banner on the bottom (~52%, i.e. text banner >50%)**, separated by a **CURVED gold line** (a quadratic Bézier, concave/dips-at-centre — NOT a straight horizontal line; the straight line was explicitly rejected). Banner fill `#0E1116`, gold trim `#C8A24A` ~9px on the curve. Tune `BEDGE`/`BCTRL` in the script (BEDGE=banner-top-y at edges, BCTRL=control-y at centre; BCTRL>BEDGE ⇒ concave).
- **BIG yellow `#F4C842` 2-line headline that FILLS the banner** — operator (2026-07-09 v4): *"lot of empty space in the text box… increase the font size."* Size each badge's fs so the widest line nearly spans the banner (fs ~160–200, tuned per badge since word lengths differ; `bottom≈182`, banner raised to `BEDGE=450/BCTRL=545` to give the bigger text room). Don't leave big empty margins. Ring redrawn deterministically as always.
  - ⚠ **Verify clearance by MEASURING, not eyeballing:** the banner is a lens (curve on top, ring-circle on the bottom) so it narrows toward the ring — the **bottom line** clips first. Detect the bright-text pixels (`r>230 & g>185 & b<110`, restricted to `y>470` so the gold curve `#C8A24A` and photo highlights don't pollute) and keep their **max radial distance from centre ≤ ~460** (ring inner edge `r_in≈475`). Ease that badge's fs or raise `bottom` if it exceeds.
- **CLICKY copy (not bare 2-word labels):**
  - **Commodity:** `{commodity} में तेजी` / `{commodity} में मंदी` (e.g. `लाल मिर्च / में तेजी`). Reference-style `{commodity} तेज़` also fine.
  - **FMCG:** communicate the ACTUAL offer when it's small/simple (e.g. `जार पर 2 / साबुन फ्री`, like the ref `साबुन 4 पर 1 फ्री`); otherwise `{product} पर स्कीम`. **Never** the generic "फ्री स्कीम".
  - **News:** a mini-headline with a hook (`{subject} से {benefit}`, e.g. `ई-श्रम से / ₹2 लाख`, like the ref `LPG से रोक हटी`) — never a bare 2-word phrase like "मुफ्त बीमा".
- Gemini still supplies ONLY the subject photo (subject-only circle, no banner/text); we composite the banner + curve + text + ring. Same ring-normalize (crop 90%r → D=1080) as before.
- ⚑ **PHOTO MUST FILL THE FRAME (operator, 2026-07-09 v6).** The top image is **full-bleed `object-fit:cover`** (fills the ENTIRE top space, no bars). Since cover crops to the top ~half, the photo must be a **dense overhead flat-lay that fills the whole square with stuff, edge to edge, no empty background/bare table** — so the top crop always looks full and normal. Prompt for "abundant flat-lay completely filling the frame corner to corner, no empty background." ❌ **Do NOT** use `object-fit:contain` + blurred side-fill — the operator rejected that as "off / boxy / empty-looking side bars."
- **Line spacing:** `.t` line-height ~1.1 + `.t div{margin:7px 0}` so the two lines don't touch each other; keep the radial-clearance check so neither line touches the ring.
- ⚑ **UNIFORM text size across the set (operator, 2026-07-09 v7):** use ONE `FS` constant for all 3 badges (not a per-badge fs) so they look like a set. Pick the largest FS that keeps EVERY badge's widest line within radial clearance — the tightest badge caps it. Target radial ≤ ~448 (ring inner ≈454; more margin than the old 460 — operator said text was still grazing the border).
- ⚑⚑ **LOCKED STANDARD (operator, 2026-07-13): `FS=166`, `bottom=135`, CENTERED in the banner.** Two things were wrong and are now fixed in `kc-badge-banner.py`:
  - **Centering:** raising `bottom` to clear the ring (the old 205) seated the 2-line block in the banner's UPPER half, leaving an empty dark gap below — the "text drifting to the top" the operator saw in-app. The block must be centered in the *dark banner*, not just clear of the ring. Set `bottom ≈ 325 − (2·FS·1.1 + 14)/2` (the block-centering formula; ≈135 at FS166). **Do NOT push `bottom` up to fix a ring-clip — lower `FS` instead**, or the top-drift comes back.
  - **Size:** operator wants the text BIG enough to fully cover the banner. Swept uniform FS with the centering formula: **166 is the largest that keeps every badge's widest line clear of the inner white ring** (measured max radial 439 ≤ 448; FS174 → 453 = clip-risk). So FS166 is the cap for typical 2-word lines; if a day's copy has a wider line, drop FS a notch and re-measure. Always re-run the radial check (`r>230 & g>185 & b<110`, `y>470`) after any FS/copy change.
- ⚑ **FMCG badge = the REAL product/freebie photo (operator, 2026-07-09 v7):** for the FMCG badge, don't use a generic AI still-life — use the ACTUAL scheme product image. Best source = the D2R post's own media: `SELECT attachment FROM ugc_posts p JOIN ugc_posts_stats s ON p.post_id=s.post_id WHERE s.published_id='<fmcg news_id>'` (community DB) → `attachment` JSON `[{media_url}]` (a `storage.googleapis.com/compressed-user-posts/...` retailer photo; `attachment_media_type` tells image vs video). `curl` it, crop a SQUARE framing the product + offer label so the label lands in the visible top zone (not cropped by the banner), save as `subjfull_2.png`. (Today: Center Fruit candy jar with the "GET 2N Godrej NO.1 SOAP worth ₹10 with this jar" label — the real product + freebie.) This overrides the "badges are generic even for FMCG" rule for the FMCG badge.
  - ⚑ **If the D2R post photo is blurry / product not clearly visible (operator, 2026-07-09 v8): DON'T use it — source a CLEAN high-res image from the internet of the exact product OR the freebie.** Use WebSearch → WebFetch a retail page for the direct image URL. **IndiaMART (`imimg.com`) is reliably `curl`-able and serves 1000×1000 by swapping the URL's `-250x250.jpg` size token → `-1000x1000.jpg`** (BigBasket/Amazon pages tend to 403 for WebFetch). Match the EXACT freebie variant (today the label said "Godrej No.1 **Lime Aloe Vera**" → used the clean Godrej No.1 Lime Aloe Vera pack, not the Sandal-Turmeric one). Crop so the brand face lands in the visible top zone (not hidden by the banner). The operator's words: "exact product OR freebie image" — a clear freebie shot is acceptable.
  - ⚑ **SHARPNESS IS NON-NEGOTIABLE (operator, 2026-07-09 v9): the top image must be VERY CLEAR — never upscale a small sub-crop.** The blur came from cropping a ~700px region of a 1000px source and blowing it up 1.5× to 1080. imimg caps at 1000×1000 and `m.media-amazon.com` is blocked, so 1000px is the ceiling. To stay sharp: take a **FULL-WIDTH band** of the source (1000→1080 is only ~1.08×, imperceptible) that contains the brand, `resize` it with `Image.LANCZOS`, paste it at the TOP of the 1080² `subjfull` canvas, and fill the hidden bottom (behind the banner) with dark `#0E1116`. Keep any upscale ≤ ~1.1×. Verify the brand text is crisp at full size AND at the ~104px thumbnail before publishing.

## ⚑⚑ FINAL BADGE DESIGN (2026-07-07 — full image + gradient scrim + BIG short-hook text) — ⚠ SUPERSEDED 2026-07-09 (see above), kept for history

The design landed here after operator (Hritik + Harsh) iteration on 2026-07-07. **Gemini supplies ONLY the circular subject photo; we composite the text.** The old hard dark banner + gold line was rejected ("horizontal line division doesn't look good", "image must stay visible — Zomato-style overlay"). The final look:
- **Full-circle product photo** fills the whole badge (generate the badge as a subject-only circle: subject fills the circle, small directional tag, **NO banner, NO text**).
- **Soft bottom gradient scrim** (transparent→dark, `rgba(11,13,17,…)`) fades in only at the bottom so the image stays visible and there is **no hard line**.
- **BIG yellow `#F4C842` text** with a drop shadow sitting over the gradient — the main element in the lower half.
- Flat ring redrawn deterministically (red `#B92B0F` 4.5% + white 1.5%).

⚠ **"65% area" is not physically achievable with readable text in a circle** — the readable ceiling is ~30–35% of the badge area; past that the text clips the ring (verified). The reference samples ("इलायची तेज़", "साबुन 4 पर 1 फ्री", "LPG से रोक हटी") look huge because they are **short 2–3 word hooks**. **So keep each badge headline to short 2-line hooks** (e.g. लहसुन / तेज़ · फ्री माल / स्कीम · सस्ता / माल) — short wording is what lets the font be large. This is the operator's chosen "Option D".

⚑ **BIGGER-TEXT LEVERS (operator, 2026-07-09 — "still <50%, make it bigger").** When 2-word lines at fs~150 still read too small, push size with these knobs (all now baked into `kc-badge-banner.py`): (1) **use SINGLE-word lines** — one word per line (मिर्च / तेज़ · फ्री / स्कीम · ₹2 लाख / बीमा), the biggest single lever since fewer glyphs → bigger fs; (2) **fs ~240–250** for 1-word lines (~200–210 when a line is a wider number like ₹2 लाख); (3) **widen the text box** (`.t` side padding 40→18px) and drop letter-spacing to 0; (4) **line-height ~0.94**; (5) **raise `bottom` to ~132** so the block sits in the circle's WIDER middle-lower zone (not the narrow bottom); (6) **use the `TALL` gradient** (darkens from ~8%) so the higher-seated big text still sits on a dark scrim. Always re-verify no ring clip on the widest line (the number line) at full size AND a ~104px strip.

**Flow per day** (`KC Stories/kc-badge-banner.py`, headless Edge + `Nirmala UI`, same engine as `kc-card-render.py`):
1. Generate 3 **subject-only circular** badges (full-circle photo, tag, no banner/text) → ring-normalize (detect circle, crop interior ~90%r, rescale to common diameter D=1080) → `subjfull_1/2/3.png`.
2. Edit the `BADGES`/variant list: `src` = subjfull png, `lines=[…]` = **short 2-line hook** (each line is nowrap), `fs` per badge tuned so nothing overflows the ring. Use the `HARD` gradient preset + `bottom≈108`.
3. Run it → `vD_<i>.png` (or your tag). **Verify:** read a contact sheet at full size AND a **~104px collapsed strip** (the notification/story-row size) — text must stay readable small AND not clip the ring. Bump/cut `fs` per badge until clean (garlic-type badges with no yellow in the photo measure cleanest).
4. Upload `vD_<i>.png` for the entry badges; build the transparent square PN export from `vD_<i>.png`.

⚠ **curl upload paths on this box:** use **forward-slash** Windows paths in `-F "file=@C:/Users/.../final_1.png"` — the backslash form intermittently fails with curl error 26.
⚠ Circle-width constraint: the circle narrows toward the bottom, so a long lower line clips first — keep lines short, shorter word on line 2, drop `fs` if it touches the ring.

---

## OPENING LINE (verbatim, every badge)

> Create a clean circular story-style icon / badge in a 1:1 square ratio, similar to an Instagram story highlight thumbnail, with a pure white background #FFFFFF outside the circle and no outer border or frame.

---

## CONSISTENCY LINE (verbatim, every badge)

> IMPORTANT CONSISTENCY: thin flat solid warm outer ring, thin white inner ring, a tall dark curved bottom banner (about 40% of the circle's height) with subtle golden trim, carrying a VERY LARGE / oversized bold Devanagari headline that fills almost the entire banner width, premium poster look, all content tightly clipped inside the circle.

---

## OUTER RING (verbatim, every badge)

> THE OUTER RING MUST BE IDENTICAL ACROSS A SET OF THREE BADGES, so it is a FLAT SOLID single colour — uniform brick-red **#B92B0F** with NO gradient, NO shading, NO highlights, NO colour variation anywhere around the ring. It is a perfectly concentric annulus of UNIFORM thickness equal to about **4.5% of the badge's overall diameter** — the same width at the top, bottom, left and right, never tapering. No Instagram pink, no purple, no pastel tints.

## INNER FRAME

> A thin white circular ring of uniform width (about 1.5% of the diameter) sits just inside the solid red outer ring for separation.

## MAIN IMAGE (per badge)
- **Subject:** the commodity / product / news visual (cumin heap, LED bulbs, vegetables under monsoon clouds, etc.) on **dark slate or weathered wood**, warm daylight from upper-left.
- **Floating tag** upper-right: small white price/rupee tag.
- **Directional accent on tag:** RED ↑ for तेज़ी · GREEN ↓ for मंदी · YELLOW ⚠️ for news/alert · YELLOW नया for new launch · white "₹X फायदा" tag for margin stories.
- **1–2 props** max. No people, no logos, no brand labels.

## BOTTOM TEXT BANNER (tall, LARGE text, may wrap to two lines)

> A tall dark near-black curved banner about **40% of the circle's height** (taller than before — bumped 2026-07-06) with a subtle golden trim line above it, hugging the bottom inside of the inner ring. A bold single Devanagari headline in **Mukta ExtraBold**, **VERY LARGE / OVERSIZED — the text must FILL the banner: each line runs nearly edge to edge (about 85–90% of the banner's inner width) and the one or two lines together fill most of the banner's height. Make the headline as BIG as possible while staying fully inside the banner** — never small, never leaving large empty margins; allowed to wrap to two lines and never shrunk to fit or clipped by the curve. **RENDER THE ENTIRE HEADLINE IN WARM YELLOW #F4C842 — every word yellow (the punchline word may be slightly bolder/brighter). NEVER use white font in the banner.**
> ⚑ **BIG-TEXT RULE (operator, 2026-07-06):** earlier badges had the banner text too small (~half the size it should be, leaving big empty banner margins). The headline must be dramatically larger — it should visually dominate the banner and read clearly as a thumbnail. Reference size: like the sample badges "इलायची तेज़", "साबुन 4 पर 1 फ्री", "LPG से रोक हटी" — huge two-line yellow text filling the banner.

> ⚑ **NO WHITE BANNER TEXT (operator rule, 2026-06-25).** The operator removes the badge background in a post-step; any white banner text disappears when the bg is knocked out. So all banner text must be the warm yellow #F4C842 (a non-white colour that survives bg removal) — never white, never near-white/cream. This replaces the old "punchline yellow, the rest white" guidance.

**Examples** (whole phrase yellow #F4C842, bold = the brighter/heavier punchline word): "तेल भाव **गिरा**" · "जीरा भाव **तेज़**" · "**₹840 फायदा** LED बल्ब" · "सब्ज़ियां **महंगी**" · "मानसून **कम बारिश**"

---

## STYLE NOTES (verbatim close)

> STYLE: crisp, polished, high-contrast, premium. No exclamation marks, no extra emoji beyond the directional arrow/warning on the tag, no logos, no brand labels, no watermark, no date.
> Output: a single square PNG with a pure white background outside the circle and no outer border.

---

## DIRECTION → BADGE QUICK MAP
| Category | Tag marker | Yellow word example |
|---|---|---|
| Commodity (तेज़ी) | RED ↑ on ₹X | "तेज़", "बढ़ी", "महंगा" |
| Commodity (मंदी) | GREEN ↓ on ₹X | "गिरा", "मंदी", "सस्ता" |
| FMCG (new launch) | YELLOW नया | "नया लॉंच" |
| FMCG (rate/margin) | white "₹X→₹Y" or "₹X फायदा" | "रेट कटी", "फायदा" |
| News (warning) | YELLOW ⚠️ | "महंगी", "कम बारिश", "अलर्ट" |
| News (policy) | YELLOW info dot | "नया नियम" |

## WHAT NOT TO DO
- ❌ Gradient ring (drifts across badges — use FLAT solid #B92B0F) · ❌ thick ring (>5% of diameter) · ❌ skipping the post-gen normalize composite · ❌ Instagram pink/purple or pastel ring · ❌ outer border/frame · ❌ multiple focal elements · ❌ KC logo or brand labels · ❌ exclamation marks · ❌ "happy shopkeeper" faces · ❌ clutter beyond ONE subject + ONE tag + 1–2 props · ❌ **white (or near-white/cream) banner text — it vanishes when the operator removes the bg; banner text is always warm yellow #F4C842.**
