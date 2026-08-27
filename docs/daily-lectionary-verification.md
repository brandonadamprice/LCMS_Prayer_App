# Verifying `daily_lectionary.json`

`devotions/data/daily_lectionary.json` was checked row by row against the
published daily lectionary at <https://wartburgproject.org/daily>, which serves
the same two-reading plan (one OT, one NT) one date at a time at
`https://wartburgproject.org/daily/YYYY-MM-DD`.

## How the check was run

The file is keyed two ways — liturgical keys for the movable season
(`Ash Wednesday` … `Holy Trinity`) and fixed dates (`18 May` … `09 Mar`) for the
rest — so keys were compared by resolving them to calendar dates first:

1. For each date, `ChurchYear.get_liturgical_key` gives the key the app would
   look up, exactly as `utils.get_daily_lectionary_reading_for_date` does.
2. `2026-03-10` … `2027-03-09` covers 357 of the 400 keys. The remaining 43 —
   `10 Feb`–`09 Mar` and `18 May`–`31 May`, which the movable season hides in
   those two years — were each sampled in the first later year where the date
   resolves to its fixed key. Most land in 2028–2038; `18 May` needs the
   earliest possible Easter and only comes up in 2285. 408 dates in total,
   covering all 400 keys.
3. Both references were compared after normalising `;` vs `,` and spacing.

Two properties of the source were confirmed along the way, not assumed:

- **It is keyed the same way we are.** Keys reached in two different years
  (`Lent 3 Tuesday` on 2026-03-10 and 2027-03-02, and seven more) return the
  same readings, so its movable season tracks the liturgical day rather than the
  calendar date.
- **Its fixed-date table is stable.** 22 fixed-date keys re-sampled in 2029 and
  2033 returned what they returned in 2026.

## What it found

107 of the 800 readings differed; 97 were corrected and 10 were kept (below).
Almost all of the 97 belonged to one of four column slips, where a run of rows
had shifted and every row in the run was individually a valid reference:

| Rows | Column | Slip |
| --- | --- | --- |
| `01 Sep`–`27 Sep` | NT | Ephesians (7 readings) was missing, so the column ran seven days behind and re-read 2 Corinthians 7–12 |
| `28 Sep`–`01 Nov` | NT | Matthew 16–18 and 21:1-22 were missing; Matthew 1–2 appeared here as well as at Christmas |
| `12 Dec`–`24 Dec` | NT | an extra `2 John 1-13; 3 John 1-15` row (this plan omits 2–3 John and Philemon) pushed Jude through Revelation back a day |
| `12 Aug`–`15 Aug`, `23 Oct`–`01 Nov` | OT | an extra row and a missing one in each stretch (`2 Samuel 5:1-25`, `Deuteronomy 34:1-12`) |

Two isolated rows named a verse that does not exist — `09 Jan` OT
`Ezekiel 3:12-28` (Ezekiel 3 ends at verse 27) and `31 Jan` NT
`2 Timothy 3:1-18` (2 Timothy 3 ends at 17). The rest were
single rows whose end verse differed (`21 Feb` OT, `06 Dec` OT,
`Lent 1 Tuesday` NT, `Lent 3 Sunday` OT, `Easter 3 Thursday` OT).

## Divergences deliberately kept

The source is not infallible, so it was adopted everywhere except where doing so
would introduce a defect. Verse counts below were checked against the EHV reader
on the same site (`/read?q=<book> <chapter>`).

| Row | Ours (kept) | Theirs | Why ours stands |
| --- | --- | --- | --- |
| `27 Feb` OT | `Job 30:16-31` | `Job 20:16-31` | Job 20 ends at verse 29, so theirs cannot be fetched; the column is in Job 30 on either side |
| `05 Sep` OT | `2 Kings 2:19-25; 4:1-7` | `… 4:1-17` | theirs runs into `2 Kings 4:8-22` on `06 Sep` |
| `22 Jul` OT | `1 Samuel 5:1-6:3; 10-16` | `… 5:10-16` | theirs re-reads verses inside its own first range; the printed `10-16` continues into 1 Samuel 6 (21 verses) |
| `30 Dec` OT | `Isaiah 58:1-59:3; 14-21` | `… 58:14-21` | same shape; `14-21` continues into Isaiah 59 (21 verses) |
| `08 Jun`, `09 Jun`, `06 Mar`, `07 Mar` NT | `John 12:20-36a`, `John 12:36b-50` | `12:20-36`, `12:37-50` | the half-verse split is the printed form and the app already renders it |
| `04 Dec` OT | `Isaiah 10:12-27a; 33-34` | `10:12-27, 33-34` | same |
| `16 Oct` OT | `Deuteronomy 14:1-2; 22-23; 14:28-15:15` | `… 28-15:15` | the same reference, written with the chapter repeated |

## Keeping it correct

A shifted column is invisible to per-row checks, because each shifted row is
still a well-formed reference. What catches it is
`test_no_reading_is_read_twice_in_one_year` in
`devotions/python/tests/test_lectionary_keys.py`: a slip makes some reading come
up twice in the same year. It walks 2026–2045.

Note that `John 5`–`13` appear twice in the *file* by design, on `18 May`–`11 Jun`
and again on `14 Feb`–`09 Mar`. Those are the two ends of the fixed-date block,
and the movable season always covers one end or the other, so no single year
reaches both — which is what that test pins down.
