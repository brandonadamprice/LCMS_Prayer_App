# Verifying `daily_lectionary.json`

`devotions/data/daily_lectionary.json` has been checked reading by reading
against two independent sources. It now matches the printed LSB table on 798 of
its 800 readings; the two exceptions are deliberate and are listed below.

## The two sources

**The printed LSB Daily Lectionary** is the table this file derives from, and is
the authority here. A scan of it is on Hymnary as [LSB #299][hymnary], but the
readings there exist only as page images behind a bot-protection challenge. The
same table is published as a text PDF by [St. John's, Austin][pdf], which is
what was actually used.

**[wartburgproject.org/daily][wp]** serves the same plan one date at a time at
`/daily/YYYY-MM-DD`, rendering each reading's full text. It is a convenient
second opinion and it is what first exposed the column slips below, but it is a
transcription and carries its own errors — see "Where the site differs" at the
end.

[hymnary]: https://hymnary.org/hymn/LSB2006/299
[pdf]: https://www.stjohnsaustinlcms.org/wp-content/uploads/2018/06/LSB-Daily-Lectionary.pdf
[wp]: https://wartburgproject.org/daily

## How each check was run

Against the **PDF**, the comparison is positional. The table's four columns
(day label, OT, NT, Additional Reading) sit at fixed x offsets within each page,
so cells were assigned to columns by offset and the OT/NT pair read off each
row. This matters: the Additional Reading column is often scripture too, so
reading cells in sequence pairs the wrong ones together. Rows also split across
page boundaries — a day label ends one page and its readings begin the next — so
a row missing its readings carries forward. That yields exactly 400 rows, which
line up one to one with this file's 400 keys in file order.

Against the **site**, keys had to be resolved to dates first, since this file is
keyed two ways: liturgical keys for the movable season (`Ash Wednesday` …
`Holy Trinity`) and fixed dates (`18 May` … `09 Mar`) for the rest.
`ChurchYear.get_liturgical_key` gives the key the app would look up, exactly as
`utils.get_daily_lectionary_reading_for_date` does. `2026-03-10` … `2027-03-09`
covers 357 of the 400 keys; the other 43 are hidden by the movable season in
those years and were each sampled in the first later year where the date
resolves to its fixed key (mostly 2028–2038; `18 May` needs the earliest
possible Easter and only comes up in 2285). 408 dates, covering all 400 keys.

Two properties of the site were confirmed rather than assumed: keys reached in
two different years return the same readings, so its movable season tracks the
liturgical day rather than the calendar date; and 22 fixed-date keys re-sampled
in 2029 and 2033 returned what they returned in 2026.

## What the checks found

Both sources agreed that four runs of this file's readings had slipped. Every
row in a slipped run was individually a valid, fetchable reference, which is why
nothing had caught them:

| Rows | Column | Slip |
| --- | --- | --- |
| `01 Sep`–`27 Sep` | NT | Ephesians was missing entirely, so the column ran seven days behind and re-read 2 Corinthians 7–12 |
| `28 Sep`–`01 Nov` | NT | Matthew 16–18 and 21:1-22 were missing; Matthew 1–2 appeared here as well as at Christmas, where it belongs |
| `12 Dec`–`24 Dec` | NT | an extra `2 John 1-13; 3 John 1-15` row pushed Jude through Revelation back a day |
| `12 Aug`–`15 Aug`, `23 Oct`–`01 Nov` | OT | an extra row and a missing one in each stretch (`2 Samuel 5:1-25`, `Deuteronomy 34:1-12`) |

The NT column reads a book straight through, so those slips also left holes.
The OT column skips constantly by design — 53 of a year's 364 consecutive pairs
leave a gap, the largest 51 verses — because the plan covers only about a third
of the Old Testament in a year. The NT column, by contrast, leaves just four
gaps all year. Apparent holes in the NT are usually not holes at
all: 1 Corinthians 14–16 and 2 Corinthians 10–13 look skipped between `22 Aug`
and `01 Sep`, but the PDF's Additional Reading column carries them on `22 Aug`
and `31 Aug`. This file does not model that third column.

Two references also named a verse that does not exist, and one reading was far
too short. Those are covered below.

## Deliberate differences from the printed table

Two rows depart from LSB, both because LSB prints a verse that is not there.
The app fetches these references from the ESV API, so the printed form would
come back short or empty.

| Row | This file | LSB prints | Why |
| --- | --- | --- | --- |
| `09 Jan` OT | `Ezekiel 3:12-27` | `Ezekiel 3:12-28` | Ezekiel 3 ends at verse 27 |
| `31 Jan` NT | `2 Timothy 3:1-17` | `2 Timothy 3:1-18` | 2 Timothy 3 ends at verse 17 |

Everything else in the file matches the printed table.

## Where the site differs from the printed table

Recorded so the next person does not "fix" this file toward the site. In all of
these LSB is right and the site is not; the two rows above are the only places
the reverse holds.

| Row | LSB and this file | wartburgproject.org |
| --- | --- | --- |
| `Lent 1 Tuesday` NT | `Mark 3:20-35` | `Mark 3:20-25` — 6 verses, and leaves 3:26-35 unread |
| `Lent 3 Sunday` OT | `Genesis 27:30-45; 28:10-22` | `… 28:10-20` |
| `Easter 3 Thursday` OT | `Exodus 38:21-39:8; 22-23; 27-31` | `Exodus 38:21-39:8` |
| `22 Jul` OT | `1 Samuel 5:1-6:3; 10-16` | `… 5:10-16`, re-reading verses inside its own first span |
| `05 Sep` OT | `2 Kings 2:19-25; 4:1-7` | `… 4:1-17`, running into the next day's `4:8-22` |
| `06 Dec` OT | `Isaiah 14:1-23` | `Isaiah 14:1-12` |
| `13 Dec` NT | `Revelation 1:1-19` | `Revelation 1:1-20` |
| `30 Dec` OT | `Isaiah 58:1-59:3; 14-21` | `… 58:14-21`, same shape as `22 Jul` |
| `21 Feb` OT | `Job 16:1-21` | `Job 16:1-22` |
| `27 Feb` OT | `Job 30:16-31` | `Job 20:16-31` — Job 20 ends at verse 29, and the site's own page renders a single verse for it |

The site also rounds LSB's half-verse splits to whole verses (`John 12:20-36a` /
`12:36b-50` and `Isaiah 10:12-27a`). This file keeps the printed form, which the
app already renders.

## Keeping it correct

Three properties are now tested, each catching a class of defect the others
cannot see:

- **`test_no_reading_is_read_twice_in_one_year`**
  (`test_lectionary_keys.py`) walks 2026–2045 and fails if any year reaches the
  same reference twice. This is what catches a slipped column, whose individual
  rows all look fine. Note that `John 5`–`13` appear twice in the *file* by
  design, at the two ends of the fixed-date block (`18 May`–`11 Jun` and
  `14 Feb`–`09 Mar`); the movable season always covers one end or the other, so
  no single year reaches both, which is what the test pins down.
- **`test_no_reading_runs_past_the_end_of_its_chapter`**
  (`test_daily_lectionary_data.py`) catches the two LSB misprints above and
  anything like them.
- **`test_reading_lengths_stay_in_a_sane_band`** (same file) catches a dropped
  digit. Readings run 10–37 verses (OT) and 8–31 (NT) against a plan that aims
  at 15–25; the site's `Mark 3:20-25` would have been 6.

The last two need to know how long each chapter is, so
`devotions/python/tests/chapter_verse_counts.json` records the last verse of
every chapter this lectionary draws on, read off the EHV text on
wartburgproject.org. Verse counts vary slightly between translations at a
handful of chapter ends, so treat a single-verse discrepancy there as a question
about the table rather than proof of a bad reading.
