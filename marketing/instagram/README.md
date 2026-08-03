# Instagram Ads — A Simple Way to Pray

Ready-to-post Instagram ad creative for [asimplewaytopray.com](https://asimplewaytopray.com),
generated from the app's own brand assets (palette, Lora/Montserrat type, and the
season banners in `devotions/static/`).

**The rendered creative lives in Google Drive, not in git:**
[Social Media / Instagram](https://drive.google.com/drive/folders/1G8dcPDklGEX9el93Xdc77nzGM0xGX9W-)
([stills](https://drive.google.com/drive/folders/1OTlMGCXFeXOCLAMV3TZNQc4Mfn3xmEZj) ·
[reels](https://drive.google.com/drive/folders/1ixRlrfAgIDwsCYT41NPwTGeEzB9iRG25)).
The repo keeps the sources so anything can be re-rendered; the PNGs and MP4s are
build output and are gitignored.

## What's here

```
src/         HTML/CSS sources + render.js (regenerate any time)
src/fonts/   locally-cached Lora & Montserrat webfonts (OFL) — offline rendering
ad_copy.md   campaign copy: captions, headlines, hashtags, creative angles
stills/      render output, gitignored — 1080x1350 PNG (4:5), feed posts / ads
reels/       render output, gitignored — 1080x1920 MP4 (9:16, 30fps, H.264)
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
