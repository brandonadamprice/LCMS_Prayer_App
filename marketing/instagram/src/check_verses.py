#!/usr/bin/env python3
"""Checks every verse on a card against a Bible text.

Two modes, in order of usefulness:

  --esv DIR   Exact check. Each card must be a contiguous substring of its
              referenced verse(s), ignoring case, punctuation and quote style.
              This is the one that catches a compressed or reordered quote.

  --asv FILE  Fallback. Scores word overlap against the ASV (1901), which sits
              upstream of the ESV via the RSV. Catches a wrong reference or a
              badly drifted quote; will not catch a small elision.

Neither corpus is vendored — see PROOFING.md for why, and for the fetch
commands. Run after any copy change:

    python3 check_verses.py --esv /tmp/esv
    python3 check_verses.py --asv /tmp/asv.json
"""
import argparse
import json
import os
import re
import sys
import unicodedata

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

# The corpus numbers books in Roman and titles a few differently.
ROMAN = {"1": "i", "2": "ii", "3": "iii"}
ASV_ALIASES = {"psalm": "psalms", "revelation": "revelation of john",
               "song of solomon": "song of songs"}


def flatten(text):
    """Case, punctuation and quote style stripped — what an exact match means here."""
    text = unicodedata.normalize("NFKD", text)
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'),
                 ("”", '"'), ("—", "-"), ("–", "-")):
        text = text.replace(a, b)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def words(text):
    out = []
    for w in re.findall(r"[a-z']+", text.lower().replace("’", "'")):
        w = ARCHAIC.get(w, w)
        if w not in STOP:
            out.append(w)
    return out


def parse_ref(ref):
    """'Genesis 22:8' / 'Lamentations 3:22-23' -> (book, chapter, [verses])."""
    ref = ref.replace("–", "-").replace("—", "-")
    m = re.match(r"^\s*(.+?)\s+(\d+):(\d+)(?:-(\d+))?\s*$", ref)
    if not m:
        return None
    ch, v0, v1 = int(m.group(2)), int(m.group(3)), m.group(4)
    return m.group(1).strip(), ch, list(range(v0, int(v1) + 1 if v1 else v0 + 1))


def load_esv(directory):
    """mdbible layout: one Book.md per book, '## Chapter N', then 'N. text'."""
    verses = {}
    for name in os.listdir(directory):
        if not name.endswith(".md"):
            continue
        book, chapter = name[:-3].lower(), None
        for line in open(os.path.join(directory, name), encoding="utf-8"):
            head = re.match(r"^##\s+Chapter\s+(\d+)", line)
            if head:
                chapter = int(head.group(1))
                continue
            body = re.match(r"^(\d+)\.\s+(.*)$", line.strip())
            if body and chapter:
                verses[(book, chapter, int(body.group(1)))] = body.group(2).strip()
    return verses


def load_asv(path):
    doc = json.load(open(path, encoding="utf-8"))
    return {
        (book["name"].lower(), ch["chapter"], v["verse"]): v["text"]
        for book in doc["books"] for ch in book["chapters"] for v in ch["verses"]
    }


def asv_book(book):
    book = book.lower()
    lead, _, rest = book.partition(" ")
    if lead in ROMAN and rest:
        book = f"{ROMAN[lead]} {rest}"
    return ASV_ALIASES.get(book, book)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esv", help="directory of mdbible Book.md files")
    ap.add_argument("--asv", help="path to an ASV.json")
    ap.add_argument("--min", type=float, default=0.45, help="ASV overlap threshold")
    args = ap.parse_args()
    if not (args.esv or args.asv):
        sys.exit("Give --esv DIR or --asv FILE; see the docstring.")

    exact = bool(args.esv)
    if exact:
        corpus, key = load_esv(args.esv), lambda b: ("psalms" if b.lower() == "psalm"
                                                     else b.lower())
    else:
        corpus, key = load_asv(args.asv), asv_book

    cards = json.load(open(CARDS, encoding="utf-8"))["cards"]
    bad, missing = [], []
    for card in cards:
        parsed = parse_ref(card["ref"])
        if not parsed:
            missing.append((card, "reference did not parse"))
            continue
        book, ch, vs = parsed
        texts = [corpus.get((key(book), ch, v)) for v in vs]
        if not all(texts) if exact else not any(texts):
            missing.append((card, f"not in corpus: {book} {ch}:{vs[0]}"))
            continue
        joined = " ".join(t for t in texts if t)
        if exact:
            if flatten(card["verse"]) not in flatten(joined):
                bad.append((card, None, joined))
        else:
            ref_words = set(words(joined))
            cw = words(card["verse"])
            score = sum(w in ref_words for w in cw) / len(cw) if cw else 1.0
            if score < args.min:
                bad.append((card, score, joined))

    for card, why in missing:
        print(f"?? plate {card['plate']:3d}  {card['ref']}: {why}")
    for card, score, text in bad:
        tag = "not a contiguous quote" if score is None else f"overlap {score:.2f}"
        print(f"!! plate {card['plate']:3d}  {card['ref']}  {tag}")
        print(f"     card: {card['verse']}")
        print(f"     text: {text[:200]}")

    label = "exact" if exact else f"above {args.min:.2f} overlap"
    print(f"\n{len(cards) - len(bad) - len(missing)}/{len(cards)} {label}; "
          f"{len(bad)} to fix, {len(missing)} unresolved")
    return 1 if (bad or missing) and exact else 0


if __name__ == "__main__":
    sys.exit(main())
