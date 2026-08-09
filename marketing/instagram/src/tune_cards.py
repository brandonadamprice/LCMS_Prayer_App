#!/usr/bin/env python3
"""Computes the per-card crop and scrim for the verse cards, from the plates.

Six cards could be tuned by eye. A hundred cannot, and eyeballing them would not
be reproducible anyway — so the three visual knobs are derived from the plate
itself and written back into verse-cards.json, where they stay reviewable in the
diff:

    focus   object-position, aimed so the engraving's subject lands *below* the
            verse instead of behind it
    bright  exposure, so a plate printed on bright paper and one printed almost
            black both land on the same mood — this is what keeps a hundred
            cards looking like one campaign
    scrim   how hard to darken the top of the plate so the verse holds contrast
    long    drop the verse to the smaller size when it runs past ~90 characters

Run after editing any verse text; hand edits to those fields are overwritten.

    python3 tune_cards.py [--check]

--check exits non-zero if anything would change, for use in CI.

Requires Pillow.
"""
import json
import os
import sys

from PIL import Image

SRC = os.path.dirname(os.path.abspath(__file__))
CARDS = os.path.join(SRC, "verse-cards.json")
PLATES = os.path.join(SRC, "art", "plates.json")

# Must match shared.css.
PANEL_W, PANEL_H = 1080, 1010
TEXT_TOP, TEXT_BOTTOM = 170, 520      # where the verse actually sits
CONTRAST = 1.36                       # .plate-art filter
SCRIM_L = 25 / 255                    # rgba(20, 25, 40) luminance
TARGET_L = 0.30                       # composite the verse needs to sit on
TARGET_PANEL = 0.34                   # mean exposure every plate is pulled to
BRIGHT_RANGE = (0.42, 0.95)           # how far exposure may push a plate
SUBJECT_AT = 0.70                     # put the subject this far down the panel
LONG_AT = 90                          # characters


def contrasted(v):
    """Luminance 0-1 after contrast, before exposure."""
    return min(1.0, max(0.0, (v - 0.5) * CONTRAST + 0.5))


def row_stats(im):
    """Per-row (mean, detail) over the source plate, normalised 0-1."""
    w, h = im.size
    px = im.load()
    means, details = [], []
    step = max(1, w // 160)            # sampling 160 columns is plenty
    for y in range(h):
        vals = [px[x, y] / 255 for x in range(0, w, step)]
        m = sum(vals) / len(vals)
        means.append(m)
        details.append((sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5)
    return means, details


def tune(path, verse):
    im = Image.open(path).convert("L")
    w, h = im.size
    means, details = row_stats(im)

    scale = PANEL_W / w                # cover: these plates are all taller than 4:5
    scaled_h = h * scale
    slack = max(0.0, scaled_h - PANEL_H)

    # Doré's subject is the region that carries the contrast, so weight rows by
    # how much detail they hold and take the centroid.
    weight = sum(details) or 1.0
    centroid = sum(y * d for y, d in enumerate(details)) / weight   # source px

    # Place that centroid SUBJECT_AT down the panel; object-position is the
    # fraction of the slack cropped off the top.
    want_top = centroid * scale - SUBJECT_AT * PANEL_H
    focus_y = 0.5 if slack <= 0 else min(1.0, max(0.0, want_top / slack))

    # Rows actually visible after the crop.
    top_px = focus_y * slack
    v0 = max(0, min(h - 1, int(top_px / scale)))
    v1 = max(v0 + 1, min(h, int((top_px + PANEL_H) / scale)))
    panel = [contrasted(v) for v in means[v0:v1]] or [0.5]
    panel_l = sum(panel) / len(panel)

    # Exposure: pull every plate's mean onto the same mood. Without this the
    # bright-paper plates read as pale grey next to the near-black ones and the
    # set stops looking like one campaign.
    bright = TARGET_PANEL / panel_l if panel_l > 0 else 1.0
    bright = min(BRIGHT_RANGE[1], max(BRIGHT_RANGE[0], bright))

    # With crop and exposure fixed, how bright is the band the verse lands on?
    y0 = max(0, min(h - 1, int((top_px + TEXT_TOP) / scale)))
    y1 = max(y0 + 1, min(h, int((top_px + TEXT_BOTTOM) / scale)))
    band = [min(1.0, contrasted(v) * bright) for v in means[y0:y1]] or [0.5]
    band_l = sum(band) / len(band)

    # Solve the alpha that brings the band down to TARGET_L, then undo the
    # gradient's falloff (the verse sits around 0.9 of --scrim-top).
    if band_l <= TARGET_L:
        alpha = 0.35
    else:
        alpha = (band_l - TARGET_L) / (band_l - SCRIM_L)
    scrim = min(0.9, max(0.35, alpha / 0.9))

    return {
        "bright": round(bright, 2),
        "scrim": round(scrim, 2),
        "focus": f"50% {round(focus_y * 100)}%",
        "long": len(verse) > LONG_AT,
    }


def dump(doc):
    """One line per card, so the diff reads as copy rather than as JSON."""
    out = ["{", '  "_comment": ' + json.dumps(doc["_comment"], indent=2,
                                              ensure_ascii=False).replace("\n", "\n  ") + ",",
           '  "cards": [']
    lines = []
    for c in doc["cards"]:
        ordered = {k: c[k] for k in
                   ("plate", "ref", "verse", "hook", "tier", "bright", "scrim", "focus", "long")
                   if k in c}
        lines.append("    " + json.dumps(ordered, ensure_ascii=False))
    out.append(",\n".join(lines))
    out += ["  ]", "}", ""]
    return "\n".join(out)


def main():
    check = "--check" in sys.argv
    doc = json.load(open(CARDS, encoding="utf-8"))
    plates = {p["plate"]: p for p in json.load(open(PLATES, encoding="utf-8"))["plates"]}

    changed = []
    for card in doc["cards"]:
        plate = plates[card["plate"]]
        before = {k: card.get(k) for k in ("bright", "scrim", "focus", "long")}
        card.update(tune(os.path.join(SRC, "art", plate["file"]), card["verse"]))
        after = {k: card.get(k) for k in ("bright", "scrim", "focus", "long")}
        if before != after:
            changed.append((card["plate"], plate["title"], before, after))

    if check:
        for n, title, b, a in changed:
            print(f"plate {n:3d} {title}: {b} -> {a}")
        print(f"{len(changed)} card(s) out of date" if changed else "up to date")
        return 1 if changed else 0

    open(CARDS, "w", encoding="utf-8").write(dump(doc))
    print(f"tuned {len(doc['cards'])} cards, {len(changed)} changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
