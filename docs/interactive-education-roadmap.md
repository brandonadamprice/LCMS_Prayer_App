# Interactive Education Features — Roadmap

Companion features to the Bible Family Tree (`/bible_family_tree`) and the
Church Year Wheel (`/church_year_wheel`, shipped July 2026). Each follows the
same pattern: a fully self-contained template (embedded styles + data + D3
from the d3js.org CDN), a plain route in `routes/devotions.py`, an Education
menu entry in `menu.py`, and a sitemap entry in `routes/misc.py`. No changes
to `static/app.js` / `styles.css` are needed (so no `?v=` bumps), and dark
mode is handled with `body.dark-mode` CSS overrides — no JS redraw.

## 1. Bible History Timeline — DRAFT EXISTS, NOT WIRED

`devotions/templates/bible_timeline.html` is a complete first draft that is
**not yet reachable** (no route, menu, or sitemap entry) and **not yet
verified in a browser**. It contains:

- A pan/zoom horizontal timeline (d3.zoom, x-axis only) from the patriarchs
  (~2100 BC) to the apostolic age (AD 100), with 12 era bands, ~70 people
  bars in three lanes (Patriarchs/Judah kings, Israel kings, Prophets &
  Apostles), and ~26 event diamonds — each with a short description and
  scripture reference in a click-to-open detail tip.
- Kings colored by evaluation (faithful / mixed / evil); overlapping bars
  represent coregencies. Pre-monarchy dates follow the traditional 1 Kgs 6:1
  reckoning (early Exodus, 1446 BC) and are labeled approximate.
- Search, era quick-jump buttons, zoom controls, label culling at low zoom.

Remaining work: add the route (`/bible_timeline`), menu + sitemap entries,
verify in the browser (label collisions, mobile bottom-sheet tip, dark mode),
sanity-check dates/descriptions, then commit.

## 2. Bible Journeys Map

An interactive, self-contained SVG map (no tile services — works offline with
the PWA) with toggleable routes: the Exodus, Jesus' ministry, and Paul's
missionary journeys. Click a stop for the scripture reference and a sentence
of context. Stylized coastline of the eastern Mediterranean / Sinai drawn as
SVG paths; numbered stops along each route; route colors per journey with a
legend and per-route toggle buttons like the family tree's controls.

## 3. Tabernacle Explorer

A labeled SVG cutaway diagram of the tabernacle (courtyard, altar of burnt
offering, laver, Holy Place with lampstand / table of showbread / altar of
incense, veil, Most Holy Place with the ark). Click each element for its
function (Exodus 25–40 refs) and its Christological fulfillment (Hebrews
8–10, John 1:14 "tabernacled among us", etc.) — typology in the Lutheran
tradition. Smallest-scope feature of the three; a good single-page project.

## Local verification recipe

Boot the real app without Secret Manager (secrets_fetcher reads env first):
set dummy values for `FLASK_SECRET_KEY`, `GOOGLE_CLIENT_ID/SECRET`,
`ESV_API_KEY`, `FIREBASE_*`, `FACEBOOK_*`, and a **valid** `FERNET_KEY`
(generate with `Fernet.generate_key()`), then run a small script that inserts
`devotions/python` on `sys.path`, `os.chdir`s there, imports `main`, and
calls `main.app.run(port=5057)`. Anonymous page renders touch no Firestore.
Point `.claude/launch.json` at the script for browser-pane verification.
