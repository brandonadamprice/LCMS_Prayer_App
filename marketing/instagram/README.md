# Instagram Ads — A Simple Way to Pray

Ready-to-post Instagram ad creative for [asimplewaytopray.com](https://asimplewaytopray.com),
generated from the app's own brand assets (palette, Lora/Montserrat type, and the
season banners in `devotions/static/`).

## What's here

```
stills/   1080x1350 PNG (4:5) — Instagram feed posts / ads
reels/    1080x1920 MP4 (9:16, 30fps, H.264) — Reels & Stories
src/      HTML/CSS sources + render script (regenerate any time)
```

### Stills (feed, 4:5)

| File | Concept |
| --- | --- |
| `stills/01-hero.png` | Brand hero — app icon, name, tagline, CTA |
| `stills/02-daily-office.png` | "Pray the hours" — the four daily offices |
| `stills/03-bible-in-a-year.png` | Bible in a Year — streaks & grace days |
| `stills/04-church-year.png` | Liturgical seasons — Lent/Easter imagery |

### Reels (9:16, 14s, silent)

| File | Concept |
| --- | --- |
| `reels/01-a-day-of-prayer.mp4` | Morning → Midday → Evening → Close of Day → CTA |
| `reels/02-everything-for-prayer.mp4` | Title → animated feature list → CTA |

The reels are rendered without audio — add a music track from Instagram's
licensed library when publishing (audio bundled into the file would need its
own license).

## Suggested captions

**Hero / general:**
> Begin the day in the Word. Daily offices, Scripture, and the Small Catechism —
> in the rhythm of the Church Year. Free on web & Android. 🔗 asimplewaytopray.com

**Daily office:**
> Morning. Midday. Evening. Close of Day. Four short services to shape your day
> around prayer — each one ready when you are. #dailyprayer #lutheran

**Bible in a Year:**
> The whole Bible, one day at a time — with streaks that come with grace days,
> because life happens. Start today at asimplewaytopray.com

**Suggested hashtags:**
`#lutheran #lcms #dailyprayer #dailyoffice #devotions #bibleinayear
#smallcatechism #liturgy #christianapp #prayerlife`

## Regenerating

Requires Node with Playwright (+ Chromium) and any ffmpeg with libx264
(`pip install imageio-ffmpeg` is enough — the script finds it automatically).

```sh
cd marketing/instagram/src
NODE_PATH=$(npm root -g) node render.js            # everything
NODE_PATH=$(npm root -g) node render.js --stills-only
NODE_PATH=$(npm root -g) node render.js --reels-only
```

Stills are plain 1080x1350 pages screenshotted by Chromium. Reels are pure-CSS
animations on a fixed 14-second timeline; the script pauses every animation,
seeks frame-by-frame at 30fps, and encodes the frames with ffmpeg. Everything is
deterministic, so re-renders are pixel-stable.

`src/fonts/` holds locally-cached Lora and Montserrat webfonts (SIL Open Font
License) so rendering works offline.
