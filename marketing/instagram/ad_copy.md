# Instagram ad creatives + copy — A Simple Way to Pray

This folder is the home for the asimplewaytopray.com social creatives. The
visuals are rendered from the app's own brand assets (palette, Lora/Montserrat
type, and the season banners in `devotions/static/`) by
`marketing/instagram/src/render.js` in the LCMS_Prayer_App repo; running
`marketing/instagram/src/sync_drive.py` pushes the rendered output straight
into this folder.

## Assets

| Placement | Files | Spec |
|---|---|---|
| Feed (4:5) — feature cards | `stills/{01-hero, 02-daily-office, 03-bible-in-a-year, 04-church-year}.png` | 1080x1350 PNG |
| Feed (4:5) — verse cards | `stills/verse-001-*.png` … `verse-100-*.png` (100) | 1080x1350 PNG |
| Reels & Stories (9:16) | `reels/{01-a-day-of-prayer, 02-everything-for-prayer}.mp4` | 1080x1920, H.264, 30fps, 14s |

The **verse cards** are built in the layout of the ASWTP "Reel Ad 2" spot, which
outperformed the rest: a dark navy field, the Scripture set large in condensed
type, and a plate underneath carrying the reference. Scripture leads, the
product line is one quiet line of positioning copy, and the URL sits in the bar
at the bottom.

There is one per plate of Gustave Doré's *Bible Gallery* (1866), duotoned into
the brand navy — public domain, so they can run in paid placements without a
licence. Each plate is chosen for the verse it carries, not for decoration; the
pairing is half the ad, and captions that name it tend to earn the comment.

**A hundred cards is a posting calendar, not an ad set.** Do not put them all in
one campaign. Two uses:

- **Paid** — pick 4–6 at a time by angle (the `hook` field groups them), run
  them as their own ad set, rotate as they fatigue. There are enough to never
  reuse a creative in a year of weekly rotation.
- **Organic** — one a day is a year and a half of grid. The whole set is dark
  navy at the same exposure, so the profile grid reads as one body of work.

**Every card carries a clearance tier** in `src/verse-cards.json`, because Doré
illustrated the whole Bible, including the parts that do not belong in a cold
paid feed:

- **`ad`** (73) — cleared for paid placement.
- **`organic`** (26) — fine on the grid, wrong for a cold audience. Violence,
  corpses, or a scene that needs its context: the Deluge, Jezebel, the Massacre
  of the Innocents, the Flagellation, Death on the Pale Horse.
- **`hold`** (1) — plate 98. Its 1866 caption names an ethnic group as the mob;
  the card is rendered with a neutral title, but publishing it at all is a
  decision for a person, not a default.

`node render.js --stills-only --tier=ad` renders just the paid-ready set.

**The verse text on these has not been diffed against an actual ESV** — see
`src/PROOFING.md`. Read the verse against esv.org before a card goes out. Once
per card, forever.

**On the Full of Eyes art from Reel Ad 2:** their gallery is published under
CC BY-NC-ND, which rules out both paid placement (NonCommercial) and laying copy
over the image (NoDerivatives). Running it again in an ad needs written
permission from the artist — worth asking for, since it is the best art this
brand has had, but not something the licence grants on its own.

The reels are rendered **silent** — add a music track from Instagram's licensed
library when publishing (audio bundled into the file would need its own
license).

The four earlier ASWTP video ads (Clouds, Chaos, Reel Ad 2, Insta Reel Ad) sit
one level up, in `Social Media/`.

Destination link on every ad and post:

> **https://asimplewaytopray.com**

The Android build is the same site in a Capacitor shell (`com.hallowedgains.aswtp`),
so the website URL works as the single CTA for both web and app installs.

## Creative angles

- **01-hero** — brand introduction: app icon, name, tagline, CTA. The broad
  top-of-funnel static.
- **02-daily-office** — "pray the hours": Morning, Midday, Evening, Close of
  Day. The strongest hook for people already looking for structured prayer.
- **03-bible-in-a-year** — reading plan, streaks, and grace days. Aim at the
  habit/consistency audience; grace days are the differentiator.
- **04-church-year** — liturgical seasons. Narrower, but the highest-affinity
  angle for confessional Lutheran and liturgical audiences.
- **01-a-day-of-prayer** (reel) — Morning → Midday → Evening → Close of Day →
  CTA. Broad top-of-funnel spot.
- **02-everything-for-prayer** (reel) — title → animated feature list → CTA.
  Better for people comparing prayer apps.

The 100 verse cards are not enumerated here — `src/verse-cards.json` is their
source of truth, and the `hook` field is the angle. The six worth naming, because
they are the strongest pairings in the set and the pattern to copy when picking
more:

- **verse-052** (Ps 55:17 · Daniel in the Lions' Den) — the daily-office angle,
  led by the verse the offices are built on, over the man who kept them three
  times a day. The broadest of the verse cards.
- **verse-049** (Dan 6:10 · Daniel) — the same idea said plainly: "he got down on
  his knees three times a day." The most literal statement of what the app is.
- **verse-091** (Lam 3:22–23 · The Angel at the Sepulchre) — grace days and
  starting over, on resurrection morning. Aim at people who have broken a streak
  in some other app.
- **verse-064** (Matt 11:28 · Christ Stilling the Tempest) — Close of Day. Rest
  given in the middle of the storm rather than after it; the strongest single
  image in the set.
- **verse-063** (Matt 6:9 · Sermon on the Mount) — the Lord's Prayer over the
  sermon that gave it. The catechism angle, and the one to lead with for
  confessional Lutheran audiences.
- **verse-096** (Acts 12:5 · The Deliverance of St. Peter) — "earnest prayer for
  him was made by the church," over a prison door opening. The prayer wall,
  argued rather than described.

Run the four feature statics in one ad set and let Meta optimize. Run the verse
cards as their own ad set rather than mixing them in — they are a different
promise (Scripture first, product second) and will train the algorithm toward a
different audience.

Scripture is quoted from the ESV, credited on every card. ESV permission covers
quotation of this scale without written request; keep the "ESV" mark on any new
card.

Doré needs no credit legally, but naming the plate in the caption is cheap and
performs — this audience knows the engravings. A tail line works:

> Art: Gustave Doré, *Christ Stilling the Tempest* (1866).

## Primary text (feed caption) options

**A — brand / hero (pairs: 01-hero, reel 01)**

> Begin the day in the Word. Daily offices, Scripture, and the Small Catechism —
> in the rhythm of the Church Year. Free on web & Android.
> 🔗 asimplewaytopray.com

**B — daily office (pairs: 02-daily-office, reel 01)**

> Morning. Midday. Evening. Close of Day. Four short services to shape your day
> around prayer — each one ready when you are. asimplewaytopray.com

**C — Bible in a Year (pairs: 03-bible-in-a-year)**

> The whole Bible, one day at a time — with streaks that come with grace days,
> because life happens. Start today at asimplewaytopray.com

**D — church year (pairs: 04-church-year)**

> Advent, Lent, Easter, and every season between — prayers and readings that
> change with the Church Year, not just the calendar. asimplewaytopray.com

**E — everything for prayer (pairs: reel 02)**

> Daily offices, the psalter, Luther's Small Catechism, a prayer wall, and
> reminders that actually show up. Everything for prayer, in one place, free.
> asimplewaytopray.com

### Captioning a verse card

There are a hundred cards and there will not be a hundred hand-written captions.
The ones above (A–E) still cover the feature statics; verse cards take a formula,
because the card has already done the work:

> **1.** One line that says what the pairing means — *not* a repeat of the verse,
> which is already six inches tall above it.
> **2.** One line of product, concrete.
> **3.** `asimplewaytopray.com`
> **4.** Optional tail: `Art: Gustave Doré, *Title* (1866).`

Never re-type the verse in the caption. It is on the image, and repeating it is
the single most common way these posts read as filler.

Six worked examples, one per angle — copy the shape, not the words:

**F — daily office (verse-052, Ps 55:17)**

> "Evening and morning and at noon" is not a mood, it is a schedule. Four short
> offices, each one ready when you are.
> asimplewaytopray.com
> Art: Gustave Doré, *Daniel in the Lions' Den* (1866).

**G — grace days (verse-091, Lam 3:22–23)**

> Missed a day? His mercies are new every morning — and so are your grace days.
> A reading plan that lets you begin again instead of starting over.
> asimplewaytopray.com

**H — Bible in a Year (verse-092, Ps 119:105)**

> A lamp lights the next step, not the whole road. That is about how much Bible
> anyone can take in a day, so that is how it is served.
> asimplewaytopray.com

**I — Close of Day (verse-064, Matt 11:28)**

> Rest is offered in the storm, not after it. Close of Day is a short office of
> confession, psalm, and the Nunc Dimittis — the oldest way there is to fall
> asleep. asimplewaytopray.com

**J — catechism (verse-063, Matt 6:9)**

> He was asked how to pray and he answered in seven petitions. Luther's Small
> Catechism walks them one at a time, a question a day.
> asimplewaytopray.com

**K — prayer wall (verse-096, Acts 12:5)**

> Peter was in prison and the church was praying. That is the whole mechanism.
> Put a name on the wall and other people carry it with you.
> asimplewaytopray.com

## Headline (single line, shows under the creative)

- Pray the hours. Free.
- The whole Bible, one day at a time.
- Prayer in the rhythm of the Church Year.
- Everything for prayer, in one place.
- Morning, midday, evening, night.
- Grace days, because life happens.
- Begin again every morning.

## Hashtags (organic posts; ads generally skip them)

`#lutheran #lcms #dailyprayer #dailyoffice #devotions #bibleinayear
#smallcatechism #liturgy #christianapp #prayerlife`

## Regenerating

From the repo (needs Node with Playwright + Chromium, and ffmpeg with libx264):

```sh
cd marketing/instagram/src
python3 tune_cards.py                              # only after editing a verse
NODE_PATH=$(npm root -g) node render.js            # stills + verse cards + reels
python3 sync_drive.py                              # push to this folder
```

Stills are plain 1080x1350 pages screenshotted by Chromium. Reels are pure-CSS
animations on a fixed 14-second timeline; the script pauses every animation,
seeks frame-by-frame at 30fps, and encodes the frames with ffmpeg. Everything is
deterministic, so re-renders are pixel-stable.
