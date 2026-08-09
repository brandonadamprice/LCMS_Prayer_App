# Proofing the verse text

Every card sets a Scripture quotation in 76px type and marks it ESV. That is the
one thing on the card that cannot be a little bit wrong, so this is what has and
has not been checked.

## What has been checked

`check_verses.py` scores each card against the ASV (1901), which sits upstream of
the ESV through the RSV and shares most of its wording. Latest run:

```
100/100 references resolve to a real verse in the right book and chapter
 95/100 score above 0.45 word overlap with the ASV
```

The five below the threshold were read individually and are all ESV wording that
simply diverges from the ASV's — not misquotations:

| Card | Note |
| --- | --- |
| Lam. 3:22–23 | ASV has "Jehovah's lovingkindnesses"; ESV has "The steadfast love of the LORD" |
| Acts 27:25 | ASV "be of good cheer… I believe God"; ESV "take heart… I have faith in God" |
| 2 Pet. 2:9 | ASV "deliver the godly out of temptation"; ESV "rescue the godly from trials" |
| Judg. 16:20 | ASV renders the clause inside a longer sentence; the ESV clause is quoted alone |
| Acts 7:60 | ASV "lay not this sin to their charge"; ESV "do not hold this sin against them" |

Re-run after any copy change:

```sh
curl -sS -o /tmp/asv.json https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/ASV.json
python3 check_verses.py --asv /tmp/asv.json
```

## What has NOT been checked

**No line has been diffed against an actual ESV.** There is no free ESV corpus to
diff against, and the app's own ESV API needs a key that is not available to the
render pipeline. The text was written from memory and then checked for the
failure modes the ASV *can* catch — a reference pointing at the wrong verse, a
quote that drifted far from the sense, a chapter typo. It cannot catch a card
that is a faithful paraphrase but not word-for-word ESV.

**So: read the verse on a card against esv.org before that card is published.**
It is ~15 seconds per card, and only needs doing once per card ever.

A card that has been proofed does not get a marker in `verse-cards.json` — the
file is copy, and a proofing column would rot. Track it wherever the publishing
schedule lives.

## If a verse changes

`scrim`, `focus`, `bright` and `long` are computed from the verse length and the
plate, so re-run the tuner after any copy edit or the card will render with
stale values:

```sh
python3 tune_cards.py          # rewrites verse-cards.json
python3 tune_cards.py --check  # non-zero if anything is stale, for CI
```
