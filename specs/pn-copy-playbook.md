# PN copy playbook — reverse-engineered from 16,326 shipped notifications

**Source:** `community.webengage_notification_history`. Every row carries `entity_id` (the post) plus
`titles` / `messages` as rich HTML. The copy is fully recoverable — it was never lost, just wrapped in
markup. Scraped 2026-08-17.

**The headline result: this copy is not freehand creative. It is slot-filling.** Each vertical has a
fixed 2–3 line skeleton, a small rotating pool of intensifiers/emoji/verbs, and exactly one or two
slots that depend on the post. That is why the whole thing is automatable.

## The shared grammar (all verticals)

```
LINE 1  📢 <hook>  <emoji>                 ← the only genuinely post-dependent line
LINE 2  <emoji> <detail or tease> <emoji>  ← optional
LINE 3  ✅|👀|🙄 यहाँ <पढ़ें|देखें>! <noun>👇  ← near-constant CTA
```

Invariants, held across years and every vertical:

- Line 1 opens with `📢` (or an attention emoji: 😱 🙄 😳) and ends with an emotion emoji.
- Every line is **bold**, coloured, and emoji-bracketed. Total copy is 2–3 lines, never more.
- The CTA line is **media-type aware** and this is mechanical:
  - text post → `यहाँ पढ़ें!` + `पूरी जानकारी` / `इससे जुड़ी खबर`
  - video post → `यहाँ देखें!` + `पूरी वीडियो`
- **Nothing is ever resolved in the copy.** The payoff is always a demonstrative with no referent —
  `इस प्रोडक्ट`, `इन नियमों`, `ये शुरुआत`, `इस टिप`. The curiosity gap is the product.

Colours rotate from a fixed palette (`rgb(153,0,133)` magenta is the default message colour; also
`102,0,255` · `0,85,255` · `0,51,153` · `255,0,0` · `152,0,0` · `0,87,102` · `71,102,0` · `61,0,153` ·
`102,0,88`). **Irrelevant for `duo_image`** — the image kit picks its own accent. Ignore colour when
generating image PNs.

---

## Vertical 1 — Scheme (06:30) · corpus ~549 sends

The most rigid template in the set. 12/12 sampled sends are structurally identical.

```
📢 स्कीम : <the offer, verbatim from the post> <🤩|🥳|😱|🤯>
<🙄|😱> <इस प्रोडक्ट|<brand> के इस प्रोडक्ट|<brand> के साथ> पर <मिल रहा|चल रही|मिल रही|चल रहा> <तगड़ा|धमाकेदार|शानदार|जबरदस्त> <😱|🔥|🤩|🤯>
<✅|👀> यहाँ <पढ़ें|देखें>! इससे जुड़ी पूरी <जानकारी|वीडियो>👇
```

Shipped examples:
- `📢 स्कीम : 3 की खरीद पर 1 फ़्री 🤩` / `🙄 इस प्रोडक्ट पर मिल रहा तगड़ा 😱`
- `📢 स्कीम : 1 पैकेट मॉस्किटो क़्वायल फ़्री 🥳` / `🙄 इस प्रोडक्ट पर चल रही धमाकेदार 🔥`
- `📢 स्कीम : टीवी, फ्रिज और बहुत कुछ 🤯` / `😱 जेड प्लस अगरबत्ती पर शानदार 🔥`
- `📢 स्कीम : 3 लीटर वाला कंटेनर मुफ़्त 🥳` / `🙄 फेना के साथ चल रहा जबरदस्त 😱`

**Note the deliberate grammatical truncation on line 2** — "मिल रहा तगड़ा 😱" with the noun
(ऑफर/स्कीम) *omitted*. It is not a mistake; it is the hook. Preserve it.

Only slot that needs the post: the offer phrase in line 1 (and optionally the brand in line 2).
Free/मुफ़्त quantities are stated exactly — `1 पीस`, `4 पीस`, `10 ग्राम`, `दो सेल`.

## Vertical 2 — Shop Tips (08:30) · corpus ~34 + 3 reactivation

Title promises the **outcome**; message points at a **method it refuses to name**.

```
📢|😱|🙄 <aspirational outcome for the shop> <🤩|😱>
<✅|🙄|📢> <बस करें!|बस|अभी कर लें> <इन नियमों का पालन|इन बातों का रखें ख्याल|ये छोटा सा काम|ये शुरुआत>👇
```

Shipped examples:
- `📢 दुकान की तिजोरी में बरसेगा धन 🤩` / `🙄 अभी कर लें ये छोटा सा काम👇`
- `😱 ग्राहकों की लगेगी लाइन 🤩` / `🚀 बिकेंगे लाखों के सामान 🔥` / `📢 अपनी दुकान पर करें ये शुरुआत👇`
- `🙄 लाखों में पहुंचेगी दुकान की सेल 🤩` / `✅ बस करें! इन नियमों का पालन👇`
- `📢 दुकान की सेल होगी जबरदस्त 😱` / `✅ बस इन बातों का रखें ख्याल👇`
- `📢 दुकान के लिए ₹50,000 देगी सरकार 🤩` / `✅ यहाँ पढ़ें! इससे जुड़ी पूरी जानकारी👇`

Recurring outcome nouns: `दुकान की सेल`, `ग्राहकों की लाइन/बाढ़`, `दुकान की तिजोरी`, `लाखों का माल`, `मुनाफा`.

### Reactivation variant (the 3 rows that ran as `Reactivation Exp`)
Two changes from the standard Shop Tips voice — both worth keeping:

1. **Personalisation token with a Hindi fallback**, first thing in the title:
   - `{% if user['custom']['store_name'] %}{{user['custom']['store_name']}}{% else %}आपकी दुकान{% endif %}`
   - `{% if user['system']['first_name'] %}{{user['system']['first_name']}}{% else %}सेठ{% endif %} जी`
2. **Outcome reframed as a problem, phrased as a question**, with a distress emoji (😰 😱) instead of
   an aspiration emoji:
   - `<सेठ> जी, गर्मी में स्टॉक खराब होने से परेशान हो ? 😰` / `इस एक तरीके से बच जाएगा लाखों का माल !`
   - `<सेठ> जी, ग्रामीण इलाके में नहीं चल रही किराना दुकान !😱` / `तो इन टिप्स को अजमाएं और मुनाफा कमाएं !`
   - `<आपकी दुकान> पर ग्राहकों की बाढ़ आने वाली है! 😱` / `बस इस टिप को अपनाइए और देखिए`

⚠️ Jinja tokens are a **WebEngage title/message feature**. They do **not** work inside `duo_image`
images — the pixels are rendered before WebEngage ever sees them. For image PNs use the generic
fallback (`सेठ जी` / `आपकी दुकान`) or drop the token.

## Vertical 3 — Mandi (13:30) · corpus ~138 sends

The most mechanical vertical. One variable slot, one constant line.

```
📢 <price move> <📉|😯|😕>
✅ यहाँ पढ़ें! तेजी-मंदी रिपोर्ट👇        ← CONSTANT. 7/7 sampled sends, verbatim.
```

Line 1 has exactly two shapes:
- **(a) numeric** — `₹<amount> <घटेंगे|बढ़ेंगे> <commodity> के <भाव|दाम>`
  `₹500 घटेंगे काबुली चना के भाव 📉` · `₹200 घटेंगे जीरा के दाम 😯` · `₹50 बढ़ेंगे चीनी के दाम 😕`
- **(b) directional** — `<commodity> में <रहेगी तेजी जारी|जारी रहेगी बढ़त>` or `आगे और बढ़ेंगे <commodity> के दाम`
  `गुड़ में रहेगी तेजी जारी 😯` · `हल्दी में जारी रहेगी बढ़त 😕` · `आगे और बढ़ेंगे किशमिश के दाम 😕`

Emoji encodes direction: `📉` falling · `😯` surprise · `😕` unwelcome. Never 🤩/🥳 — mandi news is
never celebratory.

## Vertical 4 — FMCG (time TBD) · corpus ~25 sends

The **only** vertical where the hook is genuinely written rather than slotted — which is exactly why
the tracker sheet says "see if the headline gives value and whether a clickbaity PN can be written on
it" for this row and no other.

```
📢<news hook, derived from the headline> <💥|😯|😱|🤕|❓>
[<👉|🙄|😳> <supporting detail, often a number> <📊|🏡|🥳|😱>]   ← optional, 1–2 of these
✅ यहाँ पढ़ें! इससे जुड़ी खबर👇                                  ← often but not always present
```

Shipped examples:
- `📢छोटे ब्रांड्स ने मचाया तहलका! 💥` / `👉FMCG बिक्री में 10.6% उछाल 📊` / `👉गांवों में बढ़ी जबरदस्त मांग! 🏡`
- `📢महंगाई बढ़ी, पैक हुए छोटे😯` / `✅जानें FMCG कम्पनियों का प्लान👇`
- `मंदी में क्यों नहीं रुके कदम?❓` / `🙄शहरी-ग्रामीण बाजारों में धमक🛒` / `✅यहाँ पढ़ें! इससे जुड़ी खबर👇`
- `FMCG कम्पनियों पर बड़ा आरोप😱` / `एक्सपायरी डेट पर बवाल🕵` / `मंत्रालय की नजर 👁 अब क्या होगा?🤔`
- `📢 ग्राहकों को लगेगा झटका 🫤` / `😳 महंगे होंगे खाने के सामान 😱`

Two devices this vertical uses and the others don't: a **question title** (`क्यों नहीं रुके कदम?❓`,
`अब क्या होगा?🤔`) and a **hard number** in line 2 (`10.6% उछाल`). Framing is consistently
retailer-impact — what it does to *his* shop, his customers, his margin — never corporate news for its
own sake.

---

## Mapping onto `duo_image` (what the routine actually generates)

The 3-line skeleton maps 1:1 onto the image kit's slots. No translation layer needed:

| Copy line | Image kit slot |
|---|---|
| Line 1 (hook) | `--head` — the headline |
| Line 2 (detail/tease), if present | `--sub` — expanded image only |
| Line 3 (CTA) | the kit's CTA button — **do not** pass it as copy |

So a 2-line vertical (Mandi, most Shop Tips) → headline only, no subline. A 3-line vertical (Scheme,
some FMCG) → headline + subline. That matches the kit's existing "2 and 3 line" behaviour exactly,
and it means the CTA never needs to be written — the button already says it.

## What still needs a human answer

Nothing about copy voice. The remaining open items are unchanged from
`reactivation-pn-automation.md` §6: FMCG's send time, campaign identity (1 campaign or 4), and the
Shop Tips supply policy.
