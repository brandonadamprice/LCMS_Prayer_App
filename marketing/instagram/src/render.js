#!/usr/bin/env node
/**
 * Renders the Instagram ad compositions in this folder:
 *   - still-*.html  -> ../stills/*.png   (1080x1350, 4:5 feed)
 *   - reel-*.html   -> ../reels/*.mp4    (1080x1920, 9:16, 30fps H.264)
 *
 * Reels are pure-CSS animations on a fixed 14s timeline; frames are captured
 * deterministically by pausing every animation and seeking its currentTime.
 *
 * Usage:
 *   NODE_PATH=$(npm root -g) node render.js [--stills-only|--reels-only]
 *
 * Requires: playwright (with a Chromium install) and ffmpeg with libx264.
 * Override binaries with CHROMIUM_PATH / FFMPEG_PATH env vars.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync, execSync } = require('child_process');

function requireGlobal(name) {
    try { return require(name); } catch (e) {
        const globalRoot = execSync('npm root -g').toString().trim();
        return require(path.join(globalRoot, name));
    }
}
const { chromium } = requireGlobal('playwright');

function findFfmpeg() {
    if (process.env.FFMPEG_PATH) return process.env.FFMPEG_PATH;
    try { execSync('ffmpeg -version', { stdio: 'ignore' }); return 'ffmpeg'; } catch (e) { /* fall through */ }
    try {
        return execSync('python3 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"')
            .toString().trim();
    } catch (e) {
        throw new Error('No ffmpeg found. Install ffmpeg or `pip install imageio-ffmpeg`, or set FFMPEG_PATH.');
    }
}

const SRC = __dirname;
const OUT_STILLS = path.join(SRC, '..', 'stills');
const OUT_REELS = path.join(SRC, '..', 'reels');

const STILLS = [
    ['still-01-hero.html', '01-hero.png'],
    ['still-02-daily-office.html', '02-daily-office.png'],
    ['still-03-bible-in-a-year.html', '03-bible-in-a-year.png'],
    ['still-04-church-year.html', '04-church-year.png'],
    // Verse cards, in the style of the "Reel Ad 2" spot.
    ['still-05-evening-and-morning.html', '05-evening-and-morning.png'],
    ['still-06-new-every-morning.html', '06-new-every-morning.png'],
    ['still-07-lamp-to-my-feet.html', '07-lamp-to-my-feet.png'],
    ['still-08-i-will-give-you-rest.html', '08-i-will-give-you-rest.png'],
    ['still-09-prayer-as-incense.html', '09-prayer-as-incense.png'],
    ['still-10-pray-without-ceasing.html', '10-pray-without-ceasing.png'],
];

const REELS = [
    ['reel-01-a-day-of-prayer.html', '01-a-day-of-prayer.mp4', 14],
    ['reel-02-everything-for-prayer.html', '02-everything-for-prayer.mp4', 14],
];

const FPS = 30;

async function loadPage(page, file) {
    await page.goto('file://' + path.join(SRC, file));
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => Promise.all(
        Array.from(document.images).map((img) => img.decode().catch(() => {}))
    ));
}

(async () => {
    const mode = process.argv[2] || '';
    fs.mkdirSync(OUT_STILLS, { recursive: true });
    fs.mkdirSync(OUT_REELS, { recursive: true });

    const browser = await chromium.launch({
        executablePath: process.env.CHROMIUM_PATH || undefined,
    });

    if (mode !== '--reels-only') {
        const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
        for (const [file, out] of STILLS) {
            await loadPage(page, file);
            await page.screenshot({ path: path.join(OUT_STILLS, out) });
            console.log('still  ->', out);
        }
        await page.close();
    }

    if (mode !== '--stills-only') {
        const ffmpeg = findFfmpeg();
        for (const [file, out, duration] of REELS) {
            const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
            await loadPage(page, file);
            const frames = duration * FPS;
            const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'reel-frames-'));
            for (let i = 0; i < frames; i++) {
                await page.evaluate((tMs) => {
                    document.getAnimations().forEach((a) => {
                        a.pause();
                        a.currentTime = tMs;
                    });
                }, (i * 1000) / FPS);
                await page.screenshot({
                    path: path.join(tmp, `f${String(i).padStart(4, '0')}.png`),
                });
                if (i % 60 === 0) console.log(`${file}: frame ${i}/${frames}`);
            }
            await page.close();
            execFileSync(ffmpeg, [
                '-y', '-framerate', String(FPS),
                '-i', path.join(tmp, 'f%04d.png'),
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                path.join(OUT_REELS, out),
            ], { stdio: ['ignore', 'ignore', 'inherit'] });
            fs.rmSync(tmp, { recursive: true, force: true });
            console.log('reel   ->', out);
        }
    }

    await browser.close();
})();
