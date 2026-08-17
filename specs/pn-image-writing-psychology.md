# The writing psychology of KC image PNs — from 168 shipped duo_image notifications

**Corpus:** every `duo_image` PN sent by the 6 target families between 2026-07-18 and 2026-08-18.
Expanded images only (collapsed is a one-line reduction of the same headline).
Index: `specs/pn-corpus-duo-image.csv` (ref → campaign, date, time, campaign_id, item_id, image URL).

| family | ref | sends | slots |
|---|---|---|---|
| Reactivation Exp (Image PN, Scheme/FMCG) | A | 32 | 08:30 |
| Reactivation Exp (Image PN, Shop/Scheme/FMCG) | B | 30 | 13:30 |
| Reactivation Exp (Image PN, Shop Tips) | C | 33 | 19:30 |
| DAU Sticky (Image PN, Scheme/FMCG) | D | 20 | 09:30 · 20:30 |
| DAU Sticky (Image PN, Shop Tips / Shop-Scheme-FMCG) | E | 45 | 09:30 · 20:30 |
| Youtube Videos Image (Shop Tips - Duo Image) | Y | 8 | 12:30 · 13:30 |

## Where these live — and why the DB was the wrong place to look

**None of these 168 PNs are in `webengage_notification_history`.** They are built by hand in the
WebEngage UI, so the pipeline never sees them. They are only readable through the WebEngage REST API:

```
GET /v1/accounts/in~58adcc4a/push-notifications?sdks=2&q=<title substring>&pageNo=N
GET /v1/accounts/in~58adcc4a/push-notifications/<campaign_id>
```

`sdks=2` is Android (0 and 1 return nothing). `q=` filters on title. Page size is capped at 10.
The detail response carries `variations[].custom[]` → `template_type` + `entity` (the item id) +
`notification_data` (the two image URLs), plus `scheduler.time` and `segmentId`. That is the full
input the automation needs to reproduce, and it is all reachable.

Sizes in the wild are **mixed — 1000×750 (4:3) and 1000×500 (2:1)**. The kit renders 4:3, which is the
majority and the correct target.

---

## The core mechanic: the PN is not a summary of the post. It is the post with the answer removed.

This is the single rule that explains almost every image in the corpus. The source post states a fact
completely; the PN restates it with the operative detail **deleted** and a pointer where the detail
used to be.

| post (source of truth) | PN (what shipped) | what was deleted |
|---|---|---|
| "मैगी दो बड़े पैक के साथ एक गिलास का बाउल फ्री मिलता है" | `'मैगी' के साथ 'मुफ़्त' सरप्राइज़ गिफ्ट` / `2 बड़े पैक के साथ` / `❓ क्या मुफ़्त मिल रहा है` | **the gift itself** — becomes "सरप्राइज़" + a question |
| "कोलगेट ₹10 वाली के एक पैकेट में 12+1 का फ्री स्कीम" | `₹10 वाले कोलगेट पर बहुत बड़ी मुफ्त स्कीम चल रही है` | **the 12+1 ratio** → "बहुत बड़ी" |
| "फ्री✅ चिलर/फ्रिजर के लिए Campa कोल्डड्रिंक" | `क्या आपको 'फ्री' फ्रीज़र चाहिए?` / `'फ्री' फ्रीज़र पाने की प्रक्रिया` | **the brand and the how** → "प्रक्रिया" |
| "प्रोडक्ट: Pani wala nariyal / क्या बदलाव है: रेट" | `अगर 'नारियल' खरीदना है ?` / `नारियल 'महंगा' हो गया 😱` / `अभी नया 'रेट' देखें ✅` | **the rate** — direction kept, number withheld |

Corollary: **when the post headline is already a withholding hook, it ships nearly verbatim.**
"सिर्फ 21 दिन में खोलें अपना ग्रोसरी सुपरमार्केट" → `सिर्फ 21 दिन में अपना 'ग्रॉसरी सुपरमार्केट' खोलें`. The writer only
intervenes when the post gives too much away.

## The six moves layered on top

Beyond deletion, these are the transformations applied — usually two or three per PN.

**1. Relocate the threat to the reader's own shop.**
Post: *"फैक्ट्री में कैसे बनता है नकली पनीर?"* (a factory somewhere) → PN: `दुकान पर मिल रहा 'नकली पनीर'` ·
`किराना वालों के लिए 'अलर्ट'` · `2 मिनट में 'नुकसान' से 'बचें'`. The post is journalism; the PN makes it
*his* inventory. Same move in Y04 (`कहीं आप 'नकली शैम्पू' तो नहीं 'बेच' रहे ?`) and Y07.

**2. Escalate to consequence, and invent the stake if the post lacks one.**
Post: *"दुकान की सेल बिल्कुल कम क्यों है और कैसे सुधारें"* → PN: `'1 साल' के 'अंदर' ही 'दुकान' हो रहीं 'बंद'` ·
`क्या 'आप' भी 'कम बिक्री' से 'परेशान' हैं?` · `अपनी 'दुकान' को 'बंद' होने से 'बचाएँ'`. "Low sales" became
"shops closing within a year" — a stake that is not in the post.

**3. Turn a statement into a question aimed at the reader.**
`क्या आपको 'फ्री' फ्रीज़र चाहिए?` · `क्या आप अपने होलसेलर से 'क्रेडिट' पर स्टॉक खरीदते हैं?` ·
`सबसे सस्ता ड्राई फ़्रूट कहां मिलता है?` · `छोटे नमकीन पैकेट में कितना मुनाफा है?` ·
`होलसेलर सबसे 'सस्ता माल' कहाँ से खरीद रहे हैं?`

**4. Convert advice into a prohibition.** The strongest reframe in the set, because it implies the
reader is *already* losing money. Post: *"अंडे की खाली क्रेट बेचो कमाओ पैसा"* → PN:
`आज से 'खाली-ट्रे' फेंकना 'बंद' करो` · `'खाली' अंडे की क्रेट से हो रही 'डबल कमाई'`. Also
`'दुकान' का 'कचरा' फेंकना 'बंद' करो`.

**5. Add a peer or locality anchor** so the offer is already happening to someone like him:
`आपके इलाके के दुकानदार 'मुफ़्त' बेडशीट पा रहे हैं` · `किराना वाले, अपने इलाके की खबर` ·
`अपने इलाके के → 'सबसे सस्ते मार्केट'` · `अपने इलाके की खबर अभी देखें`.

**6. Name the audience explicitly.** Almost every PN says who it is for — `रिटेलर्स के लिए`,
`दुकानदारों के लिए`, `किराना वालों के लिए`, `छोटे किराना व्यापारियों के लिए`, `किराना वाले →`. The post rarely does.

## The money grammar (Scheme/FMCG and side-business PNs)

Two numbers in tension, always. The pattern is a **ratio, not an amount**:
`₹20 का प्रोडक्ट ₹200 में बेचो` · `₹2 में खरीदें → ₹200 में बेचें` · `₹50 का 'प्रोडक्ट', बस ₹4 में 'खरीदें'` ·
`'₹500' का 'स्टॉक' सिर्फ '₹100' में 'खरीदें'` · `₹1000 लगाया, ₹10000 कमाया` · `₹500 का माल / बस ₹100 में`.

Where there is only one number, it is a **monthly income**, always round and always achievable-sounding:
`₹60,000 महीना कमाओ` · `₹40,000 कमाओ` · `₹25,000 हर 'हफ्ते' कमाएँ` · `₹20,000 'मुफ्त' में 'कमाने' वाले बेच रहे` ·
`75000 महीने की कमाई`. Strike-through is used for contrast: `₹4,000 नहीं → ₹40,000 कमाओ`.

Entry cost is stated when it is low, to kill the objection before it forms: `₹500 से कर सकते है शुरुवात`,
`कोई किराया नहीं देना है`, `बिना 'खर्च' किए`, `बिना मशीन, बिना दुकान`.

## Typographic system (this is doing real work, not decoration)

- **Single quotes around every load-bearing word.** `'मुफ़्त'` `'डील'` `'सस्ता माल'` `'नुकसान'` `'बंद'`
  `'रेट'` `'साइड बिज़नेस'`. Roughly every third word is quoted. It reads as emphasis-by-air-quote and
  survives being skimmed at thumbnail size — the eye lands on the quoted words alone and still gets
  the message.
- **Highlight bars, not plain text.** Each line sits on its own solid slab — yellow, black, red,
  white, or pink — with the next line on a different colour. Never a single paragraph block.
- Colour = temperament: **yellow** = offer/deal, **red + 🚨/⚠️** = alert/fraud/loss,
  **green** = profit/safe/verified, **black** = neutral news.
- 2–4 lines maximum. Line 1 is the hook, the middle line adds the stake or the audience, the last line
  is the CTA.
- **Real photographs, heavily composited** — a shopkeeper mid-gesture (pointing, shocked, palm-out
  "stop", counting cash), real product packshots (Maggi, Colgate, Patanjali, Nycil, Ghadi, Dabur,
  Campa, Surf Excel), rupee notes, shop shelves. Faces carry visible emotion. This is a
  YouTube-thumbnail idiom, not a clean design-system idiom, and it is deliberate.
- **CTA is a small dark pill** — `अभी देखें →` in ~70% of the corpus, and it is placed wherever there is
  room (top-left, mid-right, bottom-centre) rather than a fixed slot. Urgent variants:
  `तुरंत देखें`, `अभी तुरंत देखें`, `यहाँ 'अभी' देखें`, `तुरंत 'क्लिक' करें`.

## Where the families actually differ

The grammar above is shared. Only these differ:

- **Scheme/FMCG (A, D)** — the subject is always a **named brand + a free item**. `मुफ़्त` is the pivot
  word and it appears in nearly every one. The withheld detail is *what* you get free or *how many*.
  Seasonal pegs are used hard: `स्कूल खुलने से पहले`, `मानसून से पहले 'मुफ़्त' - 'छाता'`, `'राखी' के 'सीज़न' में`.
- **Shop Tips (C, E)** — the subject is an **income or a loss**, never a product. Split roughly evenly
  between opportunity (`लाखों कमाने का मौका`) and threat (`'फ्रॉड'/'स्कैम' से तुरंत बचें`,
  `किराना वाले हो जाओ सावधान`). This is the family that uses first-person income claims:
  `मैंने बनाया अब तक 14 लाख`.
- **Shop/Scheme/FMCG (B)** — the mixed slot. Notably the **only** family that regularly runs a plain
  product-photo-plus-two-lines layout with no human face (B01 cashews, B03 rice, B04 egg crates).
- **Youtube Videos (Y)** — the most maximalist. Every one is a full thumbnail composite with a
  gesturing presenter, multiple stacked slabs, arrows, sirens, and a badge row along the bottom
  (`नुकसान से बचें` / `ग्राहक खोने का खतरा` / `सही पहचान`). Highest ink-per-pixel in the corpus.

## What this means for automating it

Reproducible now, from the post alone:
1. **The deletion rule** — take the post's specific (amount, ratio, gift, rate), remove it, put a
   pointer in its place. This is mechanical and it is the whole trick.
2. **Audience tag** — insert `रिटेलर्स/दुकानदारों/किराना वालों के लिए` on line 2.
3. **Quote-marking** — quote the 2–4 load-bearing words per line.
4. **Line count and CTA** — 2–4 lines, `अभी देखें →` pill, urgency variant when the post is a
   rate/alert.
5. **Colour temperament** — offer→yellow, alert→red, profit→green, news→black.

Needs a decision before it can be automated:
- **The composited-photo idiom.** The kit currently renders a clean AI background with a text card.
  This corpus is cut-out presenters, product packshots and stacked slabs. Either the kit gains a
  "thumbnail" layout family, or these PNs will look visibly different from what ships today. This is
  the biggest gap between the corpus and the tooling.
- **Move 2 (invent the stake)** — `'1 साल' के 'अंदर' दुकान हो रहीं 'बंद'` is not in the source post. An
  automated writer either gets permission to add stakes not present in the post, or it stays strictly
  faithful and loses some of the punch. Needs an explicit call.
- **Brand packshots.** Scheme/FMCG PNs show the real product. Those images come from the post; the
  standing rule is post media is reference-only and never shipped. Either that rule is relaxed for
  packshots specifically, or generated product imagery has to stand in.
