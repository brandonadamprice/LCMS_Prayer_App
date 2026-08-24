"""Capture App Store screenshots by rendering the real app at exact Apple
device resolutions with Playwright (same approach as the Play Store set in
this directory — the shell shows the live site, so these are true
screenshots).

Setup: run the Flask app locally with dummy secret env vars (see CLAUDE.md
"local smoke test" note; FERNET_KEY must be a valid Fernet key), then:

    python capture_ios_screenshots.py <outdir> iphone69
    python capture_ios_screenshots.py <outdir> ipad13

Output goes to mobile/ios/App/fastlane/screenshots/en-US/ (numbered
NN-name-device.png; `fastlane sync_store_listing` uploads them — deliver
detects the device class from the pixel size). Pick pages that render
fully logged-out; when the ESV API is unreachable the office pages are
still usable because their above-the-fold content is local liturgy text.
Capture on a date whose propers look good — the date shows in the shot.
"""
import sys
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8080"

DEVICES = {
    # App Store 6.9" slot (iPhone 16 Pro Max class): 1320x2868
    "iphone69": dict(
        viewport={"width": 440, "height": 956},
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 "
            "Mobile/15E148 Safari/604.1"
        ),
    ),
    # App Store 13" iPad slot: 2064x2752
    "ipad13": dict(
        viewport={"width": 1032, "height": 1376},
        device_scale_factor=2,
        is_mobile=False,
        has_touch=True,
        user_agent=(
            "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 "
            "Mobile/15E148 Safari/604.1"
        ),
    ),
}

PAGES = {
    "home": "/",
    "morning-prayer": "/office/morning",
    "evening-prayer": "/office/evening",
    "small-catechism": "/small_catechism",
    "prayer-weaver": "/prayer_weaver",
}

def main():
    outdir, device = sys.argv[1], sys.argv[2]
    pages = sys.argv[3:] or list(PAGES)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(**DEVICES[device])
        page = ctx.new_page()
        for index, name in enumerate(pages, start=1):
            page.goto(BASE + PAGES[name], wait_until="networkidle")
            page.wait_for_timeout(700)
            page.screenshot(path=f"{outdir}/{index:02d}-{name}-{device}.png")
            print("captured", name, device)
        browser.close()

if __name__ == "__main__":
    main()
