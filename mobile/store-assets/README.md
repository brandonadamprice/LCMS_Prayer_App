# Play Store listing assets

Generated from the real app pages (the Flask app rendered at each device
class's exact resolution — the shell shows the live site, so these are true
screenshots). Regenerate any time the design changes; the capture script
pattern is documented in the repo history (Playwright against a local
`flask run`, viewports below).

| Asset | Size | Play Console upload slot |
|---|---|---|
| `feature-graphic.png` | 1024×500 | Store listing → Feature graphic (required) |
| `phone/*.png` (5) | 1080×1920 (360×640 @3x) | Phone screenshots (2–8 required) |
| `tablet-7in/*.png` (5) | 1200×1920 (600×960 @2x) | 7-inch tablet screenshots |
| `tablet-10in/*.png` (5) | 1600×2560 (800×1280 @2x) | 10-inch tablet screenshots |

Pages shown: home, Morning Prayer, Evening Prayer, Luther's Small
Catechism, Prayer Weaver — all render fully without login or the ESV API.

Still needed separately (not in this folder): the 512×512 hi-res app icon
(export from the icon source used for `@capacitor/assets`).

Note: screenshots were captured logged-out on a dated devotion page, so
they show real daily content; if you retake them, pick a day whose
propers look good.
