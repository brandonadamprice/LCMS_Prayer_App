"""Data-integrity tests for devotions/data/daily_lectionary.json.

test_lectionary_keys.py checks that every date resolves to a key that exists
in the file. These tests check the other half: that the readings behind those
keys are usable scripture references, and that consecutive entries move
forward through a book instead of re-reading verses.

Both checks came out of a real defect. "24 Aug" carried the NT reference
"1 Corinthians 14:23-2:17" -- a range whose end chapter precedes its start,
which the ESV API cannot resolve -- and "31 Aug" carries
"2 Corinthians 2:1-22", which both overruns chapter 2 (17 verses) and
re-covers verses already read on "30 Aug" ("2 Corinthians 1:23-2:17").

Gaps are deliberate and are NOT checked: the daily lectionary skips passages
freely (e.g. "28 Oct" Matthew 15:21-39 -> "29 Oct" Matthew 19:1-15).
Overlaps are the anomaly, because the lectionary never doubles back within a
book on consecutive days.

liturgy is not imported here, so this suite is pure JSON + stdlib. Run from
the repo root:

    python -m unittest discover -s devotions/python/tests -t devotions/python
"""

import json
import os
import re
import unittest


DAILY_LECTIONARY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "data",
    "daily_lectionary.json",
)

# Books the daily lectionary may draw on, matched longest-first so
# "Song of Solomon" is not truncated to "Song" and "1 John" is not read as
# "John".
BOOK_NAMES = sorted(
    (
        "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua",
        "Judges", "Ruth", "1 Samuel", "2 Samuel", "1 Kings", "2 Kings",
        "1 Chronicles", "2 Chronicles", "Ezra", "Nehemiah", "Esther", "Job",
        "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon", "Isaiah",
        "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel",
        "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah",
        "Haggai", "Zechariah", "Malachi", "Matthew", "Mark", "Luke", "John",
        "Acts", "Romans", "1 Corinthians", "2 Corinthians", "Galatians",
        "Ephesians", "Philippians", "Colossians", "1 Thessalonians",
        "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon",
        "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John",
        "3 John", "Jude", "Revelation",
    ),
    key=len,
    reverse=True,
)

# Chapter:verse, tolerating the "36a" / "36b" half-verse suffixes the
# lectionary uses to split John 12:36.
_CHAPTER_VERSE = re.compile(r"(\d+):(\d+)[ab]?")

# Entries known to be wrong that this suite deliberately does not fail on.
# "31 Aug" is a symptom of a wider defect: the NT column runs seven days
# behind the printed LSB daily lectionary from mid-summer into the autumn
# (LSB gives 2 Corinthians 5:1-21 on 27 Aug and 2 Corinthians 9 on 31 Aug,
# both of which sit seven rows later in this file). Correcting one row in
# isolation would leave the sequence more incoherent than it already is, so
# the row stays as-is until the NT column is rebuilt from the printed table.
KNOWN_BAD_OVERLAPS = frozenset({("31 Aug", "NT")})


def book_of(reference):
  """Returns the leading book name of a reference, or None if unrecognized."""
  for book in BOOK_NAMES:
    if reference.startswith(book + " "):
      return book
  return None


def chapter_verse_span(reference):
  """Returns (first, last) chapter:verse pairs mentioned in a reference.

  Returns None for whole-book references that carry no chapter numbers at all
  ("Jude 1-25", "2 John 1-13; 3 John 1-15"), which have nothing to compare.
  """
  points = [
      (int(chapter), int(verse))
      for chapter, verse in _CHAPTER_VERSE.findall(reference)
  ]
  return (points[0], points[-1]) if points else None


class DailyLectionaryDataTest(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    with open(DAILY_LECTIONARY_PATH, "r", encoding="utf-8") as f:
      cls.data = json.load(f)
    # json.load preserves file order, which is the lectionary's own order:
    # the movable season (Ash Wednesday -> Holy Trinity) followed by the
    # fixed dates (18 May -> 09 Mar). Adjacent keys are adjacent days.
    cls.keys = list(cls.data)

  def test_every_entry_has_both_readings(self):
    for key in self.keys:
      entry = self.data[key]
      for column in ("OT", "NT"):
        self.assertIn(column, entry, f"{key!r} has no {column} reading")
        self.assertTrue(
            entry[column].strip(), f"{key!r} has an empty {column} reading"
        )

  def test_every_reading_names_a_known_book(self):
    for key in self.keys:
      for column in ("OT", "NT"):
        reference = self.data[key][column]
        self.assertIsNotNone(
            book_of(reference),
            f"{key!r} {column} {reference!r} does not start with a known book",
        )

  def test_chapter_ranges_never_run_backwards(self):
    # Catches references like "1 Corinthians 14:23-2:17", where the end
    # chapter precedes the start chapter. The ESV API returns nothing for
    # these, so the page renders an empty reading.
    for key in self.keys:
      for column in ("OT", "NT"):
        reference = self.data[key][column]
        span = chapter_verse_span(reference)
        if span is None:
          continue
        (first_chapter, _), (last_chapter, _) = span
        self.assertLessEqual(
            first_chapter,
            last_chapter,
            f"{key!r} {column} {reference!r} ends in an earlier chapter than"
            " it starts",
        )

  def test_consecutive_readings_do_not_overlap(self):
    # Within one book, each day picks up after the day before. Skipping ahead
    # is normal; doubling back means a duplicated or mistranscribed row.
    for column in ("OT", "NT"):
      for previous_key, key in zip(self.keys, self.keys[1:]):
        if (key, column) in KNOWN_BAD_OVERLAPS:
          continue
        previous_reference = self.data[previous_key][column]
        reference = self.data[key][column]
        book = book_of(reference)
        if book is None or book != book_of(previous_reference):
          continue
        previous_span = chapter_verse_span(previous_reference)
        span = chapter_verse_span(reference)
        if previous_span is None or span is None:
          continue
        self.assertGreater(
            span[0],
            previous_span[1],
            f"{key!r} {column} {reference!r} re-reads verses already covered"
            f" by {previous_key!r} {previous_reference!r}",
        )


if __name__ == "__main__":
  unittest.main()
