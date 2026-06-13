"""Regression tests for liturgy lectionary-key resolution.

Covers ChurchYear.get_mid_week_lectionary_key and full-year coverage of
get_liturgical_key against the daily lectionary. The mid-week devotion looks up
readings by the liturgical "key" returned here. Earlier code counted raw 7-day
blocks from Advent 1, which drifted by one or two weeks because the number of
Sundays after Epiphany and after Trinity varies with the date of Easter. These
tests verify that the key returned for each significant date in two contrasting
church years (2025-2026 with late Easter; 2026-2027 with early Easter) matches
the official LCMS one-year series calendar.

liturgy imports only the standard library, so this suite runs without the
google-cloud / protobuf stack (which currently can't import under Python 3.14).
Run from the repo root:

    python -m unittest discover -s devotions/python/tests -t devotions/python
"""

import datetime
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import liturgy


DAILY_LECTIONARY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "data",
    "daily_lectionary.json",
)


class MidWeekLectionaryKeyTest(unittest.TestCase):

  def _check(self, cases):
    for date, expected_key in cases:
      cy = liturgy.get_church_year(date.year)
      actual = cy.get_mid_week_lectionary_key(date)
      self.assertEqual(
          actual,
          expected_key,
          f"{date}: expected {expected_key!r}, got {actual!r}",
      )

  def test_2025_2026_church_year(self):
    # 2025-2026 has Easter on April 5, 2026 (late Easter), with two Sundays
    # after Epiphany before Transfiguration.
    self._check([
        (datetime.date(2025, 11, 30), "advent_1"),
        (datetime.date(2025, 12, 3), "advent_1"),
        (datetime.date(2025, 12, 7), "advent_2"),
        (datetime.date(2025, 12, 14), "advent_3"),
        (datetime.date(2025, 12, 21), "advent_4"),
        (datetime.date(2025, 12, 24), "advent_4"),
        (datetime.date(2025, 12, 25), "christmas_day"),
        (datetime.date(2025, 12, 28), "sunday_after_christmas"),
        (datetime.date(2026, 1, 4), "second_sunday_after_christmas"),
        (datetime.date(2026, 1, 6), "epiphany"),
        (datetime.date(2026, 1, 11), "epiphany_1"),
        (datetime.date(2026, 1, 18), "epiphany_2"),
        (datetime.date(2026, 1, 25), "transfiguration"),
        (datetime.date(2026, 2, 1), "septuagesima"),
        (datetime.date(2026, 2, 8), "sexagesima"),
        (datetime.date(2026, 2, 15), "quinquagesima"),
        (datetime.date(2026, 2, 18), "ash_wednesday"),
        (datetime.date(2026, 2, 22), "lent_1"),
        (datetime.date(2026, 3, 29), "palmarum"),
        (datetime.date(2026, 4, 5), "easter_day"),
        (datetime.date(2026, 5, 17), "exaudi"),
        (datetime.date(2026, 5, 24), "pentecost"),
        (datetime.date(2026, 5, 31), "trinity"),
        (datetime.date(2026, 6, 7), "trinity_1"),
        (datetime.date(2026, 11, 1), "trinity_22"),
        (datetime.date(2026, 11, 22), "last_sunday"),
    ])

  def test_2026_2027_church_year(self):
    # 2026-2027 has Easter on March 28, 2027 (earlier Easter), with only one
    # Sunday after Epiphany before Transfiguration, and 25 Sundays after
    # Trinity before the Last Sunday.
    self._check([
        (datetime.date(2026, 11, 29), "advent_1"),
        (datetime.date(2026, 12, 25), "christmas_day"),
        (datetime.date(2026, 12, 27), "sunday_after_christmas"),
        (datetime.date(2027, 1, 3), "second_sunday_after_christmas"),
        (datetime.date(2027, 1, 6), "epiphany"),
        (datetime.date(2027, 1, 10), "epiphany_1"),
        (datetime.date(2027, 1, 17), "transfiguration"),
        (datetime.date(2027, 1, 24), "septuagesima"),
        (datetime.date(2027, 2, 10), "ash_wednesday"),
        (datetime.date(2027, 2, 14), "lent_1"),
        (datetime.date(2027, 3, 28), "easter_day"),
        (datetime.date(2027, 5, 23), "trinity"),
        (datetime.date(2027, 10, 24), "trinity_22"),
        (datetime.date(2027, 11, 14), "trinity_25"),
        (datetime.date(2027, 11, 21), "last_sunday"),
    ])

  def test_weekday_uses_prior_sunday(self):
    # The week's reading is determined by the most recent marker, so weekdays
    # carry the prior Sunday's key.
    cy = liturgy.get_church_year(2025)
    # Tuesday after 1st after Trinity (June 7, 2026) is still trinity_1.
    self.assertEqual(
        cy.get_mid_week_lectionary_key(datetime.date(2026, 6, 9)),
        "trinity_1",
    )

  def test_festival_overrides_prior_sunday(self):
    # When Christmas Day, Epiphany, or Ash Wednesday falls between the prior
    # Sunday and the current date, the festival becomes the anchor instead.
    cy = liturgy.get_church_year(2025)
    # Friday Dec 26, 2025: prior Sunday was Advent 4 (Dec 21), but Christmas
    # Day (Dec 25) is more recent and overrides.
    self.assertEqual(
        cy.get_mid_week_lectionary_key(datetime.date(2025, 12, 26)),
        "christmas_day",
    )
    # Friday Feb 20, 2026: prior Sunday was Quinquagesima (Feb 15), but Ash
    # Wednesday (Feb 18) is more recent and overrides.
    self.assertEqual(
        cy.get_mid_week_lectionary_key(datetime.date(2026, 2, 20)),
        "ash_wednesday",
    )


class DailyLectionaryCoverageTest(unittest.TestCase):
  """The daily lectionary uses get_liturgical_key. A previous version of the
  JSON used "1 Sept" / "30 Sept" for September while every other month used
  zero-padded three-letter abbreviations ("01 Aug", "01 Oct", ...). Because
  strftime("%d %b") produces "01 Sep", every September date silently fell
  through to "Reading not found"."""

  @classmethod
  def setUpClass(cls):
    with open(DAILY_LECTIONARY_PATH, "r", encoding="utf-8") as f:
      cls.data = json.load(f)

  def test_every_day_of_year_resolves(self):
    # Walk a non-leap and a leap year and confirm every date has an entry.
    for year in (2025, 2026, 2027, 2028):
      cy = liturgy.get_church_year(year)
      day = datetime.date(year, 1, 1)
      end = datetime.date(year, 12, 31)
      while day <= end:
        key = cy.get_liturgical_key(day)
        self.assertIn(
            key, self.data, f"{day} resolved to {key!r}, which is not in the daily lectionary"
        )
        day += datetime.timedelta(days=1)


if __name__ == "__main__":
  unittest.main()
