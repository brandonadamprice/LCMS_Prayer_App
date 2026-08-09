# Proofing the verse text

Every card sets a Scripture quotation in 76px type and marks it ESV. That is the
one thing on a card that cannot be a little bit wrong, so this is what has and
has not been checked.

## Current state

```
python3 check_verses.py --esv /tmp/esv     ->  100/100 exact
python3 check_verses.py --asv /tmp/asv.json ->   95/100 above 0.45 overlap
```

Every card is now a **contiguous substring** of its referenced verse — not a
compression, not a reordering, not a stitch of two clauses. The ASV run still
flags five, and always will: those are places where ESV wording legitimately
diverges from the ASV's (`Lam. 3:22–23`, `Acts 27:25`, `2 Pet. 2:9`,
`Judg. 16:20`, `Acts 7:60`). The ESV run is the one that matters.

## What the exact check caught

Eight cards were faithful in sense but not word-for-word. All eight were
compressions of a longer verse — the failure mode a translation-overlap score
cannot see, because every word was already in the verse:

| Card | Was | Now |
| --- | --- | --- |
| Gen. 45:4 | "I am Joseph, your brother…" | "I am your brother, Joseph…" (ESV order) |
| Isa. 49:15 | two clauses with the middle elided | the closing clause alone |
| Judg. 5:3 | "I will sing to the LORD, I will sing…" | "To the LORD I will sing…" |
| Ruth 2:12 | dropped "the God of Israel" | quote ends before "under whose wings" |
| 1 Sam. 16:23 | opened with "And" not in the clause | starts at "David took the lyre" |
| 2 Sam. 18:9 | elided the mule and the branches | the clause entire |
| Isa. 6:8 | "And I said, 'Here I am! Send me.'" | "Here I am! Send me." |
| Ps. 103:2–3 | elided "and forget not all his benefits" | the two verses entire |

Several are better copy for it — Isa. 6:8 in particular is stronger at four
words than it was at seven.

## Corpora

Neither is vendored. They are checking tools, not project assets, and one of
them is a complete copyrighted translation that has no business sitting in this
repo's history.

```sh
# ESV — exact check. A third-party Markdown re-parse of the ESV.
git clone --depth 1 https://github.com/lguenth/mdbible /tmp/mdbible
mkdir -p /tmp/esv && cp /tmp/mdbible/by_book/*.md /tmp/esv/
# strip the NN_ prefix and underscores so filenames match the references
cd /tmp/esv && for f in *.md; do mv "$f" "$(echo "${f#*_}" | tr '_' ' ')"; done

# ASV — fallback overlap check, public domain
curl -sS -o /tmp/asv.json https://raw.githubusercontent.com/scrollmapper/\
bible_databases/master/formats/json/ASV.json
```

### How much the ESV corpus is worth

A lot, but it is not Crossway. Three things to hold in mind:

1. **It is third-hand.** `lguenth/mdbible` is parsed from another project's JSON,
   and its author says plainly in the README that they parsed it best-effort and
   would like bug reports. It is not an authorised or authoritative edition.
2. **It flattens the divine name.** The corpus renders the Tetragrammaton as
   "Lord", where the ESV prints L<small>ORD</small> in small caps. The check
   lowercases everything, so it cannot verify that casing. The cards use `LORD`,
   which is right, but the check is not what makes it right.
3. **It is a full redistribution of a copyrighted translation.** Fine to consult
   on a workstation; not something to commit, mirror, or ship.

The authoritative source is the ESV API the app already licenses
(`ESV_API_KEY` in Secret Manager, used by `services/scripture.py`). The render
box has no key and no network path to it, which is the only reason this
roundabout check exists. **If you ever wire an ESV API key into a CI job, replace
this whole file with a call to it.**

## One deliberate departure

Card 22 (Judg. 5:3) capitalises "To" where the ESV has "to" mid-verse. Raising
the first letter of a pull-quote is ordinary typography, not a misquote, but it
is the one place the card is not character-identical to the page.

## If a verse changes

`place`, `scrim`, `focus`, `bright` and `long` are computed from the verse length
and the plate, so re-run the tuner after any copy edit or the card renders with
stale values:

```sh
python3 tune_cards.py          # rewrites verse-cards.json
python3 tune_cards.py --check  # non-zero if anything is stale, for CI
```
