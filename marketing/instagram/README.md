# Instagram Ads — A Simple Way to Pray

Ready-to-post Instagram ad creative for [asimplewaytopray.com](https://asimplewaytopray.com),
generated from the app's own brand assets (palette, Lora/Montserrat type, and the
season banners in `devotions/static/`) plus public-domain engravings in
`src/art/`.

**The rendered creative lives in Google Drive, not in git:**
[Social Media / Instagram](https://drive.google.com/drive/folders/1G8dcPDklGEX9el93Xdc77nzGM0xGX9W-)
([stills](https://drive.google.com/drive/folders/1OTlMGCXFeXOCLAMV3TZNQc4Mfn3xmEZj) ·
[reels](https://drive.google.com/drive/folders/1ixRlrfAgIDwsCYT41NPwTGeEzB9iRG25)).
The repo keeps the sources so anything can be re-rendered; the PNGs and MP4s are
build output and are gitignored.

## What's here

```
src/         HTML/CSS sources + render.js (regenerate any time)
src/fonts/   locally-cached Lora, Montserrat & Oswald webfonts (OFL) — offline rendering
src/art/     public-domain Doré engravings + SOURCES.md (provenance & licensing)
ad_copy.md   campaign copy: captions, headlines, hashtags, creative angles
stills/      render output, gitignored — 1080x1350 PNG (4:5), feed posts / ads
reels/       render output, gitignored — 1080x1920 MP4 (9:16, 30fps, H.264)
```

### Stills (feed, 4:5)

Feature cards — the product, stated plainly:

| File | Concept |
| --- | --- |
| `stills/01-hero.png` | Brand hero — app icon, name, tagline, CTA |
| `stills/02-daily-office.png` | "Pray the hours" — the four daily offices |
| `stills/03-bible-in-a-year.png` | Bible in a Year — streaks & grace days |
| `stills/04-church-year.png` | Liturgical seasons — Lent/Easter imagery |

Verse cards — Scripture first, in the layout of the "Reel Ad 2" spot (the one
that performed): a full-bleed engraving, the verse large in condensed Oswald, a
navy plate under it carrying the reference, and the URL in the bar at the
bottom. They share the `body.verse` layout in `shared.css`, so each source file
is just a plate from `src/art/`, a verse, and one line of positioning copy.

| File | Verse | Doré plate | Angle |
| --- | --- | --- | --- |
| `stills/05-evening-and-morning.png` | Psalm 55:17 | Daniel in the Lions' Den | Daily office |
| `stills/06-new-every-morning.png` | Lamentations 3:22–23 | The Angel at the Sepulchre | Streaks & grace days |
| `stills/07-lamp-to-my-feet.png` | Psalm 119:105 | The Journey to Emmaus | Bible in a Year |
| `stills/08-i-will-give-you-rest.png` | Matthew 11:28 | Christ Stilling the Tempest | Close of Day |
| `stills/09-prayer-as-incense.png` | Psalm 141:2 | Prayer in the Garden of Olives | Church Year |
| `stills/10-pray-without-ceasing.png` | 1 Thess. 5:16–18 | The Pharisee and the Publican | Everything in one place |

The art is Gustave Doré's *Bible Gallery* (1866) — public domain, provenance and
licensing in `src/art/SOURCES.md`. The plates are monochrome and already close
to 4:5, so each one fills the panel with no crop tricks; a navy colour-blend
turns it into a duotone in the brand palette instead of a scanned book page.

Three knobs per card, all set in the card's own `<style>`:

- `--scrim-top` — how hard the top of the plate is darkened so the verse holds.
  Light plates (Emmaus) want ~0.8; already-dark ones (the tempest) want ~0.5.
- `object-position` on `.plate-art` — which slice of the plate survives the crop.
  Aim it so figures land *below* the verse rather than behind it.
- `.words.long` — drops the verse from 76px to 66px. Use it past ~90 characters.

The Gutenberg edition has 100 plates, so new cards mostly mean picking another
one and writing two lines of copy. `src/art/SOURCES.md` has the repo path they
come from.

### Reels (9:16, 14s, silent)

| File | Concept |
| --- | --- |
| `reels/01-a-day-of-prayer.mp4` | Morning → Midday → Evening → Close of Day → CTA |
| `reels/02-everything-for-prayer.mp4` | Title → animated feature list → CTA |

The reels are rendered without audio — add a music track from Instagram's
licensed library when publishing (audio bundled into the file would need its
own license).

Captions, headlines, and hashtags for each of these live in
[`ad_copy.md`](ad_copy.md), which is itself synced to the Drive folder (and
mirrored there as a Google Doc for editing).

## Rendering and publishing

Rendering requires Node with Playwright (+ Chromium) and any ffmpeg with libx264
(`pip install imageio-ffmpeg` is enough — the script finds it automatically).

```sh
cd marketing/instagram/src
NODE_PATH=$(npm root -g) node render.js            # everything
NODE_PATH=$(npm root -g) node render.js --stills-only
NODE_PATH=$(npm root -g) node render.js --reels-only

python3 sync_drive.py --dry-run                    # what would go up
python3 sync_drive.py                              # publish to Drive
```

`sync_drive.py` uploads `stills/`, `reels/`, and `ad_copy.md` into the Drive
folders above, matching by filename — an existing asset is updated in place, so
Drive links stay stable and anything already shared keeps working.

To publish the assets that used to be committed here without re-rendering them,
read them straight out of git history instead of the working tree:

```sh
python3 sync_drive.py --from-git e533d2d   # last commit that tracked them
```

Either way it needs application-default credentials carrying the Drive scope:

```sh
gcloud auth application-default login \
    --scopes=openid,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/cloud-platform
pip install google-api-python-client google-auth
```

Stills are plain 1080x1350 pages screenshotted by Chromium. Reels are pure-CSS
animations on a fixed 14-second timeline; the script pauses every animation,
seeks frame-by-frame at 30fps, and encodes the frames with ffmpeg. Everything is
deterministic, so re-renders are pixel-stable — a re-render of an unchanged
composition produces the same bytes that are already in Drive.

The four earlier ASWTP video ads (Clouds, Chaos, Reel Ad 2, Insta Reel Ad) were
made outside this pipeline and sit one level up in Drive, in `Social Media/`.
