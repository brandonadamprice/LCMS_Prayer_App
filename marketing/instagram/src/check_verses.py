#!/usr/bin/env python3
"""Sanity-checks every verse in verse-cards.json against a public-domain Bible.

This does NOT prove the ESV text is right — no free ESV corpus exists to diff
against, and the app's own ESV API needs a key. What it does catch is the class
of error that actually bites: a reference pointing at the wrong verse, a quote
that drifted, a chapter typo. It compares each card against the ASV (1901),
which sits upstream of the ESV via the RSV and so shares most of its wording.

Score is word overlap against the referenced verse(s), ignoring case, archaic
pronouns, and punctuation. Anything under the threshold is a card to read with
your own eyes — a low score is a prompt, not a verdict.

    python3 check_verses.py [--asv PATH] [--min 0.45]

Fetch the corpus once (it is not vendored — 8 MB, and only ever used here):

    curl -sS -o /tmp/asv.json https://raw.githubusercontent.com/scrollmapper/\
bible_databases/master/formats/json/ASV.json
"""
import argparse
import json
import os
import re
import sys

SRC = os.path.dirname(os.path.abspath(__file__))
CARDS = os.path.join(SRC, "verse-cards.json")

# ASV keeps the archaic forms the ESV modernised; normalising them stops every
# card from scoring low for the same uninteresting reason.
ARCHAIC = {
    "thou": "you", "thee": "you", "thy": "your", "thine": "your", "ye": "you",
    "hath": "has", "hast": "have", "doth": "does", "dost": "do", "shalt": "shall",
    "art": "are", "wilt": "will", "unto": "to", "saith": "says", "cometh": "comes",
    "jehovah": "lord", "yahweh": "lord",
}
STOP = {"the", "a", "an", "and", "of", "to", "in", "that", "is", "for", "his",
        "he", "you", "your", "my", "me", "it", "was", "with", "be", "not", "shall"}


def words(text):
    out = []
    for w in re.findall(r"[a-z']+", text.lower().replace("’", "'")):
        w = ARCHAIC.get(w, w)
        if w not in STOP:
            out.append(w)
    return out


def load_asv(path):
    doc = json.load(open(path, encoding="utf-8"))
    verses = {}
    for book in doc["books"]:
        name = book["name"].lower()
        for ch in book["chapters"]:
            for v in ch["verses"]:
                verses[(name, ch["chapter"], v["verse"])] = v["text"]
    return verses


# The corpus numbers books in Roman and titles a few differently.
BOOKS = {"1": "i", "2": "ii", "3": "iii"}
ALIASES = {"psalm": "psalms", "revelation": "revelation of john",
           "song of solomon": "song of songs"}


def canon(book):
    book = book.lower().strip()
    lead, _, rest = book.partition(" ")
    if lead in BOOKS and rest:
        book = f"{BOOKS[lead]} {rest}"
    return ALIASES.get(book, book)


def parse_ref(ref):
    """'Genesis 22:8' / 'Lamentations 3:22-23' -> (book, chapter, [verses])."""
    ref = ref.replace("–", "-").replace("—", "-")
    m = re.match(r"^\s*(.+?)\s+(\d+):(\d+)(?:-(\d+))?\s*$", ref)
    if not m:
        return None
    ch, v0, v1 = int(m.group(2)), int(m.group(3)), m.group(4)
    return canon(m.group(1)), ch, list(range(v0, int(v1) + 1 if v1 else v0 + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asv", default="/tmp/asv.json")
    ap.add_argument("--min", type=float, default=0.45)
    args = ap.parse_args()

    if not os.path.exists(args.asv):
        sys.exit(f"No ASV corpus at {args.asv} — see the docstring for the fetch command.")

    asv = load_asv(args.asv)
    cards = json.load(open(CARDS, encoding="utf-8"))["cards"]

    flagged, missing = [], []
    for card in cards:
        parsed = parse_ref(card["ref"])
        if not parsed:
            missing.append((card, "reference did not parse"))
            continue
        book, ch, vs = parsed
        texts = [asv.get((book, ch, v)) for v in vs]
        if not any(texts):
            missing.append((card, f"not in ASV: {book} {ch}:{vs[0]}"))
            continue
        ref_words = set(words(" ".join(t for t in texts if t)))
        card_words = words(card["verse"])
        if not card_words:
            continue
        score = sum(w in ref_words for w in card_words) / len(card_words)
        if score < args.min:
            flagged.append((card, score, " ".join(t for t in texts if t)))

    for card, why in missing:
        print(f"?? plate {card['plate']:3d}  {card['ref']}: {why}")
    for card, score, asv_text in sorted(flagged, key=lambda f: f[1]):
        print(f"!! plate {card['plate']:3d}  {card['ref']}  overlap {score:.2f}")
        print(f"     card: {card['verse']}")
        print(f"     ASV : {asv_text[:160]}")

    ok = len(cards) - len(flagged) - len(missing)
    print(f"\n{ok}/{len(cards)} above {args.min:.2f} overlap; "
          f"{len(flagged)} to re-read, {len(missing)} unresolved")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
