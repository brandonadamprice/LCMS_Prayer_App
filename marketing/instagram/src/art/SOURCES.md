# Artwork sources

Engravings used by the verse cards (`still-05` … `still-10`).

## Gustave Doré, *The Doré Bible Gallery* (1866)

All six plates are wood engravings after Gustave Doré (1832–1883), first
published 1866. **Public domain worldwide** — the work was published over 150
years ago and the artist died in 1883, so copyright has expired under both the
life+70 and the US pre-1929 publication rules.

Scans are from Project Gutenberg ebook #8710, *The Doré Bible Gallery,
Complete*, mirrored on GitHub by the GITenberg project:

<https://github.com/GITenberg/The-Dor--Bible-Gallery-Complete--13-Containing-One-Hundred-Superb-Illustrations-and-a-Page-of-__8710>

All 100 plates are vendored here, one per verse card. `plates.json` is the index
— plate number, display title and filename — and is what `render.js` joins
against `verse-cards.json`.

The only change from the source scans is a convert to 8-bit greyscale (the CSS
greyscales them anyway) and a re-encode at JPEG q84. That is ~17 MB for the set.
Engravings are dense high-frequency detail and barely compress — q72 saves only
3 MB and starts eating the line work the cards are made of — so the size is
accepted rather than optimised away. They are vendored rather than fetched at
render time so rendering stays offline and deterministic, the same reason the
webfonts are vendored.

No attribution is legally required, but crediting Doré in the caption is good
practice and tends to do well with this audience.

### Display titles

Titles come from the Gutenberg edition's own captions, title-cased. Four are
overridden in the generator:

| Plate | Gutenberg caption | Displayed as | Why |
| --- | --- | --- | --- |
| 24 | JEPHTHAH'S DAUGHTER AND HER COMPANIONS | Jephthah's Daughter and Her Companions | caption lacks its full stop |
| 36 | SOLOMON | Solomon | — |
| 84 | PRAYER OF, JESUS IN THE GARDEN OF' OLIVES | Prayer of Jesus in the Garden of Olives | stray punctuation in the scan |
| 98 | PAUL MENACED BY THE JEWS | Paul Menaced by the Crowd | the 1866 caption's framing is not one to reproduce in a brand asset; the card is also tiered `hold` |

The original captions are recorded here so the provenance stays honest even
though the display titles differ.

## What was considered and not used

**Full of Eyes** (fullofeyes.com) — the art in the "Reel Ad 2" spot. Their
gallery is published under **CC BY-NC-ND**: the NonCommercial term rules out
paid placements and the NoDerivatives term rules out laying ad copy over the
image. Using it again in a paid ad needs written permission from the artist
directly. Worth asking for — it is the strongest art available to this brand —
but it is not a license question that can be settled by reading the site.
