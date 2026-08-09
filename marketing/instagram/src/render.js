#!/usr/bin/env node
/**
 * Renders the Instagram ad compositions in this folder:
 *   - still-*.html        -> ../stills/*.png        (1080x1350, 4:5 feed)
 *   - verse-cards.json    -> ../stills/verse-*.png  (1080x1350, one per plate)
 *   - reel-*.html         -> ../reels/*.mp4         (1080x1920, 9:16, 30fps H.264)
 *
 * Reels are pure-CSS animations on a fixed 14s timeline; frames are captured
 * deterministically by pausing every animation and seeking its currentTime.
 *
 * Usage:
 *   NODE_PATH=$(npm root -g) node render.js [--stills-only|--reels-only]
 *                                           [--tier=ad|organic|hold]
 *
 * --tier renders only the verse cards at that clearance level; --tier=ad is the
 * set that can go straight into paid placements.
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

// Feature stills — the product stated plainly. One bespoke file each.
const STILLS = [
    ['still-01-hero.html', '01-hero.png'],
    ['still-02-daily-office.html', '02-daily-office.png'],
    ['still-03-bible-in-a-year.html', '03-bible-in-a-year.png'],
    ['still-04-church-year.html', '04-church-year.png'],
];

// Verse cards — one per Doré plate, built from verse-cards.json + the template
// rather than 100 near-identical HTML files. tune_cards.py owns scrim/focus/long.
const CARDS = path.join(SRC, 'verse-cards.json');
const PLATES = path.join(SRC, 'art', 'plates.json');
const TEMPLATE = path.join(SRC, 'verse-card.template.html');
// Written next to the sources so shared.css, art/ and fonts/ resolve as usual,
// then removed. Dotfile so sync_drive's collect() ignores it either way.
const SCRATCH = path.join(SRC, '.verse-card.html');

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
const escapeHtml = (s) => String(s).replace(/[&<>"]/g, (c) => ESCAPES[c]);

function verseCards() {
    const template = fs.readFileSync(TEMPLATE, 'utf8');
    const plates = new Map(
        JSON.parse(fs.readFileSync(PLATES, 'utf8')).plates.map((p) => [p.plate, p])
    );
    return JSON.parse(fs.readFileSync(CARDS, 'utf8')).cards.map((card) => {
        const plate = plates.get(card.plate);
        if (!plate) throw new Error(`verse-cards.json: no plate ${card.plate}`);
        const num = String(card.plate).padStart(3, '0');
        const html = template
            .replace('{{TITLE}}', escapeHtml(`Verse ${num} — ${plate.title} (${card.ref})`))
            .replace('{{SCRIM}}', card.scrim)
            .replace('{{BRIGHT}}', card.bright)
            .replace('{{FOCUS}}', card.focus)
            .replace('{{PLATE_FILE}}', plate.file)
            .replace('{{LONG}}', card.long ? ' long' : '')
            .replace('{{VERSE}}', escapeHtml(card.verse))
            .replace('{{REF}}', escapeHtml(card.ref))
            .replace('{{HOOK}}', escapeHtml(card.hook));
        return { html, out: `verse-${num}-${plate.slug}.png`, tier: card.tier };
    });
}

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

        const cards = verseCards();
        const only = (process.argv.find((a) => a.startsWith('--tier=')) || '').split('=')[1];
        try {
            for (const card of cards) {
                if (only && card.tier !== only) continue;
                fs.writeFileSync(SCRATCH, card.html);
                await loadPage(page, path.basename(SCRATCH));
                await page.screenshot({ path: path.join(OUT_STILLS, card.out) });
                console.log(`verse  -> ${card.out} [${card.tier}]`);
            }
        } finally {
            fs.rmSync(SCRATCH, { force: true });
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
