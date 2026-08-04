# Interactive Education Features — Roadmap

Companion features to the Bible Family Tree (`/bible_family_tree`) and the
Church Year Wheel (`/church_year_wheel`, shipped July 2026). Each follows the
same pattern: a fully self-contained template (embedded styles + data + D3
from the d3js.org CDN), a plain route in `routes/devotions.py`, an Education
menu entry in `menu.py`, and a sitemap entry in `routes/misc.py`. No changes
to `static/app.js` / `styles.css` are needed (so no `?v=` bumps), and dark
mode is handled with `body.dark-mode` CSS overrides — no JS redraw.

## 1. Bible History Timeline — SHIPPED (July 2026)

`devotions/templates/bible_timeline.html` is live at `/bible_timeline`
(route in `routes/devotions.py`, Education menu entry, sitemap entry) and
has been verified in a browser: desktop light/dark, mobile bottom-sheet
tip, search, era jumps, and zoom. Event labels are placed collision-free
in two passes (anchors claim space first; the rest appear as you zoom)
with a background-colored halo for legibility. It contains:

- A pan/zoom horizontal timeline (d3.zoom, x-axis only) from the patriarchs
  (~2100 BC) to the apostolic age (AD 100), with 12 era bands, ~70 people
  bars in three lanes (Patriarchs/Judah kings, Israel kings, Prophets &
  Apostles), and ~26 event diamonds — each with a short description and
  scripture reference in a click-to-open detail tip.
- Kings colored by evaluation (faithful / mixed / evil); overlapping bars
  represent coregencies. Pre-monarchy dates follow the traditional 1 Kgs 6:1
  reckoning (early Exodus, 1446 BC) and are labeled approximate.
- Search, era quick-jump buttons, zoom controls, label culling at low zoom.


## 2. Bible Journeys Map

An interactive, self-contained SVG map (no tile services — works offline with
the PWA) with toggleable routes: the Exodus, Jesus' ministry, and Paul's
missionary journeys. Click a stop for the scripture reference and a sentence
of context. Stylized coastline of the eastern Mediterranean / Sinai drawn as
SVG paths; numbered stops along each route; route colors per journey with a
legend and per-route toggle buttons like the family tree's controls.

## 3. Tabernacle Explorer — SHIPPED (August 2026)

`devotions/templates/tabernacle.html` is live at `/tabernacle` (route in
`routes/devotions.py`, Education menu entry, sitemap entry). A labeled
plan-view SVG of the tabernacle — fourteen numbered, keyboard-accessible
elements: the camp of Israel (Numbers 2 tribe standards around the fence),
courtyard fence, gate, altar of burnt offering, laver, the high priest, the
tent, the four coverings (peeled-back corner cutaway), table of showbread,
lampstand, altar of incense, veil, ark & mercy seat, and the pillar of
cloud. The scale bar states the real length (10 cubits ≈ 15 ft / 4.5 m). Each opens a detail card with its function
(Exodus 25–40 refs) and its Christological fulfillment (Hebrews 8–10,
John 1:14 "tabernacled among us", Romans 3:25 hilastērion, etc.) — typology
in the Lutheran tradition, with baptism/Supper connections on the laver and
showbread. Pure inline SVG — no D3; a hand-rolled viewBox camera gives drag
pan, pinch/wheel/button zoom, and fly-to-item on selection, so the whole
diagram fits on mobile with no side-scrolling. A "From the Camp to the Mercy
Seat" study section renders all thirteen entries as always-visible cards
(readable without interaction, and what the print stylesheet picks up; the
interactive detail card is print-hidden).

## Local verification recipe

Boot the real app without Secret Manager (secrets_fetcher reads env first):
set dummy values for `FLASK_SECRET_KEY`, `GOOGLE_CLIENT_ID/SECRET`,
`ESV_API_KEY`, `FIREBASE_*`, `FACEBOOK_*`, and a **valid** `FERNET_KEY`
(generate with `Fernet.generate_key()`), then run a small script that inserts
`devotions/python` on `sys.path`, `os.chdir`s there, imports `main`, and
calls `main.app.run(port=5057)`. Anonymous page renders touch no Firestore.
Point `.claude/launch.json` at the script for browser-pane verification.
