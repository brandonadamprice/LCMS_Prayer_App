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
| Feed (4:5) | `stills/{01-hero, 02-daily-office, 03-bible-in-a-year, 04-church-year}.png` | 1080x1350 PNG |
| Reels & Stories (9:16) | `reels/{01-a-day-of-prayer, 02-everything-for-prayer}.mp4` | 1080x1920, H.264, 30fps, 14s |

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

Run the four statics in one ad set and let Meta optimize.

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

## Headline (single line, shows under the creative)

- Pray the hours. Free.
- The whole Bible, one day at a time.
- Prayer in the rhythm of the Church Year.
- Everything for prayer, in one place.

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
