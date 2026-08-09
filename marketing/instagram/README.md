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
src/                   HTML/CSS sources + render.js (regenerate any time)
src/verse-cards.json   the 100 verse cards — plate, verse, hook, tier
src/tune_cards.py      derives each card's crop/exposure/scrim from its plate
src/check_verses.py    diffs every quotation against a Bible text (src/PROOFING.md)
src/fonts/             locally-cached Lora, Montserrat & Oswald webfonts (OFL)
src/art/               100 public-domain Doré plates + SOURCES.md, plates.json
ad_copy.md             campaign copy: captions, headlines, hashtags, angles
stills/                render output, gitignored — 1080x1350 PNG (4:5)
reels/                 render output, gitignored — 1080x1920 MP4 (9:16, 30fps)
```

### Stills (feed, 4:5)

Feature cards — the product, stated plainly:

| File | Concept |
| --- | --- |
| `stills/01-hero.png` | Brand hero — app icon, name, tagline, CTA |
| `stills/02-daily-office.png` | "Pray the hours" — the four daily offices |
| `stills/03-bible-in-a-year.png` | Bible in a Year — streaks & grace days |
| `stills/04-church-year.png` | Liturgical seasons — Lent/Easter imagery |

### Verse cards — `stills/verse-*.png`

**One hundred of them, one per plate of Doré's *Bible Gallery*.** Scripture
first, in the layout of the "Reel Ad 2" spot (the one that performed): a
full-bleed engraving, the verse large in condensed Oswald, a navy plate under it
carrying the reference, and the URL in the bar at the bottom.

There are no per-card HTML files. A card is a row in `src/verse-cards.json`:

```json
{"plate": 64, "ref": "Matthew 11:28",
 "verse": "Come to me, all who labor and are heavy laden, and I will give you rest.",
 "hook": "Close of Day — end the day in prayer", "tier": "ad",
 "bright": 0.72, "scrim": 0.36, "focus": "50% 0%", "long": false}
```

`render.js` joins that against `src/art/plates.json` and
`verse-card.template.html`. To add or change a card, edit the JSON and re-render
— the plate and the copy are the only decisions.

**Tiers.** Doré illustrated the whole Bible, including the parts that do not
belong in a cold paid feed. Every card carries a clearance level:

| Tier | Count | Meaning |
| --- | --- | --- |
| `ad` | 73 | cleared for paid placement |
| `organic` | 26 | fine on the grid, wrong for a cold audience — violence, corpses, or a scene that needs its context |
| `hold` | 1 | plate 98; needs a human decision before it is published at all |

`node render.js --stills-only --tier=ad` renders just the paid-ready set.

**The three visual knobs are computed, not eyeballed.** Six cards could be tuned
by hand; a hundred cannot, and hand-tuning would not be reproducible. So
`tune_cards.py` reads each plate and derives:

- `focus` — the crop, aimed so the engraving's subject lands *below* the verse
  instead of behind it
- `bright` — per-card exposure, pulling a plate printed on bright paper and one
  printed almost black onto the same mood. This is what keeps a hundred cards
  looking like one campaign rather than a hundred separate posts
- `scrim` — how hard to darken the top so the verse holds contrast
- `long` — drops the verse from 76px to 66px past ~90 characters

They are written back into `verse-cards.json` so they stay reviewable in the
diff. **Re-run `python3 tune_cards.py` after editing any verse**, or the card
renders with stale values; `--check` exits non-zero when anything is stale.

**The verse text checks out** — all 100 are now a contiguous substring of their
verse, diffed against an ESV text. `src/PROOFING.md` records what that check is
worth (the corpus is a third-party re-parse, not Crossway) and the eight cards it
caught, which were compressions no overlap score would have flagged.

The art is public domain; provenance, licensing and the display-title overrides
are in `src/art/SOURCES.md`.

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
NODE_PATH=$(npm root -g) node render.js --stills-only --tier=ad   # paid-ready verse cards only

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

> **One-time cleanup:** the first six verse cards were published as
> `05-evening-and-morning.png` … `10-pray-without-ceasing.png`. They are now
> `verse-052-…` … `verse-092-…` under the plate-numbered scheme. `sync_drive.py`
> matches by filename and never deletes, so the six old names will linger in
> Drive until someone removes them by hand.

Stills are plain 1080x1350 pages screenshotted by Chromium. Reels are pure-CSS
animations on a fixed 14-second timeline; the script pauses every animation,
seeks frame-by-frame at 30fps, and encodes the frames with ffmpeg. Everything is
deterministic, so re-renders are pixel-stable — a re-render of an unchanged
composition produces the same bytes that are already in Drive.

The four earlier ASWTP video ads (Clouds, Chaos, Reel Ad 2, Insta Reel Ad) were
made outside this pipeline and sit one level up in Drive, in `Social Media/`.
