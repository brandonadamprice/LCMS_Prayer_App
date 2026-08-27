"""Data-integrity tests for devotions/data/daily_lectionary.json.

test_lectionary_keys.py checks that every date resolves to a key that exists
in the file. These tests check the other half: that the readings behind those
keys are usable scripture references -- they name a real book, they do not run
backwards, they fit inside the chapter they name, they are roughly the size of
every other reading -- and that consecutive entries move forward through a book
instead of re-reading verses.

Several came out of real defects. "24 Aug" carried "1 Corinthians 14:23-2:17",
a range whose end chapter precedes its start, which the ESV API cannot resolve;
"31 Aug" carried "2 Corinthians 2:1-22", which both overran chapter 2
(17 verses) and re-covered verses already read on "30 Aug". Both were symptoms
of the NT column running several rows behind the printed table through the late
summer. The file has since been checked reading by reading against the printed
LSB Daily Lectionary and against wartburgproject.org/daily; see
docs/daily-lectionary-verification.md.

These are per-row checks, so they cannot see a whole column slipping out of
step: every row of a shifted column is a valid reference on its own. The test
that catches that is test_no_reading_is_read_twice_in_one_year in
test_lectionary_keys.py, which needs liturgy to resolve dates to keys.

Gaps are deliberate and are NOT checked: the OT column covers about a third of
the Old Testament in a year, so it skips freely (e.g. "26 Oct"
Deuteronomy 28:1-22 -> "27 Oct" Deuteronomy 29:1-29). Overlaps are the anomaly,
because the lectionary never doubles back within a book on consecutive days.

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

# Last verse of every chapter this lectionary draws on, so a reference can be
# checked against the chapter it names. Only the referenced chapters are
# listed. See docs/daily-lectionary-verification.md for where it came from.
CHAPTER_VERSE_COUNTS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "chapter_verse_counts.json"
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

# Both columns have since been checked against the printed LSB table, which
# they now match everywhere except the two misprints noted on
# test_no_reading_runs_past_the_end_of_its_chapter. The drift that needed an
# exemption is gone, so nothing is exempt from the overlap check any more.
KNOWN_BAD_OVERLAPS = frozenset()


def book_of(reference):
  """Returns the leading book name of a reference, or None if unrecognized."""
  for book in BOOK_NAMES:
    if reference.startswith(book + " "):
      return book
  return None


def segments(reference):
  """Splits a reference into (start_chapter, start_verse, end_chapter, end_verse).

  A bare second span carries on in the chapter the previous one ended in, which
  is how the printed lectionary writes "Isaiah 58:1-59:3; 14-21" (Isaiah 59:14-21)
  and "Deuteronomy 14:1-2; 22-23; 28-15:15". Returns None when any part of the
  reference does not parse, so callers can skip it rather than guess.
  """
  book = book_of(reference)
  if book is None:
    return None, None
  spans, chapter = [], None
  for part in re.split(r"[;,]", reference[len(book):]):
    part = part.strip()
    if not part:
      continue
    match = re.fullmatch(r"(\d+):(\d+)[ab]?-(\d+):(\d+)[ab]?", part)
    if match:
      chapter = int(match.group(3))
      spans.append(
          (int(match.group(1)), int(match.group(2)), chapter, int(match.group(4)))
      )
      continue
    match = re.fullmatch(r"(\d+):(\d+)[ab]?-(\d+)[ab]?", part)
    if match:
      chapter = int(match.group(1))
      spans.append((chapter, int(match.group(2)), chapter, int(match.group(3))))
      continue
    match = re.fullmatch(r"(\d+)-(\d+):(\d+)[ab]?", part)
    if match and chapter is not None:
      end = int(match.group(2))
      spans.append((chapter, int(match.group(1)), end, int(match.group(3))))
      chapter = end
      continue
    match = re.fullmatch(r"(\d+)-(\d+)", part)
    if match and chapter is not None:
      spans.append((chapter, int(match.group(1)), chapter, int(match.group(2))))
      continue
    match = re.fullmatch(r"(\d+)[ab]?", part)
    if match and chapter is not None:
      # A lone verse tacked onto the end, as in "Genesis 42:1-34; 38".
      verse = int(match.group(1))
      spans.append((chapter, verse, chapter, verse))
      continue
    return book, None
  return book, (spans or None)


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
    with open(CHAPTER_VERSE_COUNTS_PATH, "r", encoding="utf-8") as f:
      cls.verse_counts = json.load(f)
    # json.load preserves file order, which is the lectionary's own order:
    # the movable season (Ash Wednesday -> Holy Trinity) followed by the
    # fixed dates (18 May -> 09 Mar). Adjacent keys are adjacent days.
    cls.keys = list(cls.data)

  def reading_length(self, reference):
    """Number of verses a reference covers, or None if it does not parse."""
    book, spans = segments(reference)
    if not spans:
      return None
    total = 0
    for start_chapter, start_verse, end_chapter, end_verse in spans:
      chapters = self.verse_counts.get(book, {})
      if start_chapter == end_chapter:
        total += end_verse - start_verse + 1
        continue
      first = chapters.get(str(start_chapter))
      if first is None:
        return None
      total += first - start_verse + 1
      for chapter in range(start_chapter + 1, end_chapter):
        length = chapters.get(str(chapter))
        if length is None:
          return None
        total += length
      total += end_verse
    return total
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

  def test_no_reading_runs_past_the_end_of_its_chapter(self):
    # A reference whose last verse does not exist comes back short or empty
    # from the ESV API. The printed LSB table has two of these -- it gives
    # "Ezekiel 3:12-28" for a chapter that ends at 27 and "2 Timothy 3:1-18"
    # for one that ends at 17 -- and this file deliberately carries the
    # fetchable ends instead. See docs/daily-lectionary-verification.md.
    for key in self.keys:
      for column in ("OT", "NT"):
        reference = self.data[key][column]
        book, spans = segments(reference)
        if not spans:
          continue
        for _, _, end_chapter, end_verse in spans:
          last = self.verse_counts.get(book, {}).get(str(end_chapter))
          if last is None:
            continue
          self.assertLessEqual(
              end_verse,
              last,
              f"{key!r} {column} {reference!r} ends at {book} {end_chapter}:"
              f"{end_verse}, but that chapter ends at verse {last}",
          )

  def test_reading_lengths_stay_in_a_sane_band(self):
    """No reading is a fraction or a multiple of the size of its neighbours.

    The lectionary aims at 15-25 verses a reading; in practice this file runs
    10-37 (OT) and 8-31 (NT), the extremes being whole short chapters like
    Ecclesiastes 11 or self-contained scenes like Matthew 1:18-25. A reading
    far outside that is a dropped digit rather than an editorial choice: the
    wartburgproject.org page gives "Mark 3:20-25" where LSB prints
    "Mark 3:20-35", and 6 verses would be the shortest reading of the year by
    a third while leaving Mark 3:26-35 unread.
    """
    for key in self.keys:
      for column in ("OT", "NT"):
        reference = self.data[key][column]
        length = self.reading_length(reference)
        if length is None:
          continue
        self.assertTrue(
            8 <= length <= 40,
            f"{key!r} {column} {reference!r} is {length} verses, outside the"
            " 8-40 band every other reading sits in",
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
