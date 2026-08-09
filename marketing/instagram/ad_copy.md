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
| Feed (4:5) — verse cards | `stills/{05-evening-and-morning, 06-new-every-morning, 07-lamp-to-my-feet, 08-i-will-give-you-rest, 09-prayer-as-incense, 10-pray-without-ceasing}.png` | 1080x1350 PNG |
| Reels & Stories (9:16) | `reels/{01-a-day-of-prayer, 02-everything-for-prayer}.mp4` | 1080x1920, H.264, 30fps, 14s |

The **verse cards** (05–10) are built in the layout of the ASWTP "Reel Ad 2"
spot, which outperformed the rest: a dark navy field, the Scripture set large in
condensed type, and a plate underneath carrying the reference. Scripture leads,
the product line is one quiet line of positioning copy, and the URL sits in the
bar at the bottom.

Their art is Gustave Doré's *Bible Gallery* (1866), duotoned into the brand
navy — public domain, so it can run in paid placements without a licence. Each
plate is chosen for the verse it carries, not for decoration; the pairing is
half the ad, and captions that name it (see F–K) tend to earn the comment.

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
- **05-evening-and-morning** (Ps 55:17 · Daniel in the Lions' Den) — the
  daily-office angle, led by the verse the offices are built on, over the man who
  kept them three times a day. The broadest of the verse cards.
- **06-new-every-morning** (Lam 3:22–23 · The Angel at the Sepulchre) — grace
  days and starting over, on resurrection morning. Aim at people who have broken
  a streak in some other app.
- **07-lamp-to-my-feet** (Ps 119:105 · The Journey to Emmaus) — Bible in a Year;
  a road walked at dusk for the verse about a path. The brightest plate in the
  set, so it stands out in a feed of the others.
- **08-i-will-give-you-rest** (Matt 11:28 · Christ Stilling the Tempest) — Close
  of Day. Rest given in the middle of the storm rather than after it; the
  strongest single image in the set.
- **09-prayer-as-incense** (Ps 141:2 · Prayer in the Garden of Olives) —
  liturgical/Church Year affinity. Highest intent, narrowest audience.
- **10-pray-without-ceasing** (1 Thess 5:16–18 · The Pharisee and the Publican) —
  the everything-in-one-place angle, over a parable about how to pray; pairs
  with reel 02.

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

**F — Psalm 55:17 (pairs: 05-evening-and-morning)**

> "Evening and morning and at noon…" — the hours the Church has always kept.
> Morning, Midday, Evening, and Close of Day, each one short and ready when you
> are. Free at asimplewaytopray.com

**G — Lamentations 3:22–23 (pairs: 06-new-every-morning)**

> Missed a day? His mercies are new every morning — and so are your grace days.
> A reading plan that lets you begin again instead of starting over.
> asimplewaytopray.com

**H — Psalm 119:105 (pairs: 07-lamp-to-my-feet)**

> One lamp, one day at a time. The whole Bible in a year, with the day's reading
> waiting for you when you open it. asimplewaytopray.com

**I — Matthew 11:28 (pairs: 08-i-will-give-you-rest)**

> Put the day down. Close of Day is a short office of confession, psalm, and the
> Nunc Dimittis — the oldest way there is to fall asleep. asimplewaytopray.com

**J — Psalm 141:2 (pairs: 09-prayer-as-incense)**

> The evening sacrifice, still offered. Prayers and readings that keep the
> Church Year — Advent through Pentecost — without you having to look anything
> up. asimplewaytopray.com

**K — 1 Thessalonians 5:16–18 (pairs: 10-pray-without-ceasing)**

> Without ceasing is a tall order. A rhythm helps. Daily offices, the psalter,
> the Small Catechism, a prayer wall, and reminders that actually show up.
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
NODE_PATH=$(npm root -g) node render.js            # stills + reels
python3 sync_drive.py                              # push to this folder
```

Stills are plain 1080x1350 pages screenshotted by Chromium. Reels are pure-CSS
animations on a fixed 14-second timeline; the script pauses every animation,
seeks frame-by-frame at 30fps, and encodes the frames with ffmpeg. Everything is
deterministic, so re-renders are pixel-stable.
