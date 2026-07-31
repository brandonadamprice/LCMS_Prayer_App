"""Unit tests for liturgy (church-year date math).

liturgy imports only the standard library, so this suite runs without the
google-cloud / protobuf stack (which currently can't import under Python 3.14).
Run from the repo root:

    python -m unittest discover -s devotions/python/tests -t devotions/python
"""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import liturgy

D = datetime.date


class EasterTests(unittest.TestCase):
  # Known Western (Gregorian) Easter dates.
  KNOWN = {
      2000: D(2000, 4, 23),
      2005: D(2005, 3, 27),
      2008: D(2008, 3, 23),
      2016: D(2016, 3, 27),
      2024: D(2024, 3, 31),
      2025: D(2025, 4, 20),
      2026: D(2026, 4, 5),
      2027: D(2027, 3, 28),
      2030: D(2030, 4, 21),
      2038: D(2038, 4, 25),
  }

  def test_known_easters(self):
    for year, expected in self.KNOWN.items():
      self.assertEqual(
          liturgy.get_church_year(year).easter_date, expected, f"Easter {year}"
      )

  def test_easter_is_always_sunday(self):
    for year in range(1990, 2076):
      self.assertEqual(
          liturgy.get_church_year(year).easter_date.weekday(), 6, year
      )


class DerivedDateTests(unittest.TestCase):

  def test_offsets_from_easter(self):
    cy = liturgy.get_church_year(2026)
    easter = cy.easter_date
    self.assertEqual(cy.ash_wednesday, easter - datetime.timedelta(days=46))
    self.assertEqual(cy.pentecost, easter + datetime.timedelta(days=49))
    self.assertEqual(cy.holy_trinity, easter + datetime.timedelta(days=56))

  def test_ash_wednesday_is_a_wednesday(self):
    for year in range(2000, 2050):
      self.assertEqual(
          liturgy.get_church_year(year).ash_wednesday.weekday(), 2, year
      )


class Advent1Tests(unittest.TestCase):

  def test_advent1_is_sunday_in_window(self):
    for year in range(2000, 2050):
      adv = liturgy.get_church_year(year).calculate_advent1(year)
      self.assertEqual(adv.weekday(), 6, year)  # Sunday
      self.assertTrue(D(year, 11, 27) <= adv <= D(year, 12, 3), year)


class LiturgicalKeyTests(unittest.TestCase):

  def setUp(self):
    self.cy = liturgy.get_church_year(2026)
    self.easter = self.cy.easter_date  # 2026-04-05

  def test_easter_sunday(self):
    self.assertEqual(self.cy.get_liturgical_key(self.easter), "Easter Sunday")

  def test_ash_wednesday(self):
    self.assertEqual(
        self.cy.get_liturgical_key(self.cy.ash_wednesday), "Ash Wednesday"
    )

  def test_good_friday(self):
    good_friday = self.easter - datetime.timedelta(days=2)
    self.assertEqual(self.cy.get_liturgical_key(good_friday), "Good Friday")

  def test_palm_sunday(self):
    palm = self.easter - datetime.timedelta(days=7)
    self.assertEqual(self.cy.get_liturgical_key(palm), "Palm Sunday")

  def test_pentecost_sunday(self):
    pentecost = self.easter + datetime.timedelta(days=49)
    self.assertEqual(self.cy.get_liturgical_key(pentecost), "Pentecost Sunday")

  def test_holy_trinity(self):
    trinity = self.easter + datetime.timedelta(days=56)
    self.assertEqual(self.cy.get_liturgical_key(trinity), "Holy Trinity")

  def test_fixed_date_outside_movable_season(self):
    self.assertEqual(self.cy.get_liturgical_key(D(2026, 1, 1)), "01 Jan")


class ChurchSeasonTests(unittest.TestCase):
  """get_church_season boundaries across the 2025-2026 church year.

  Anchors: Advent 1 2025 = Nov 30 2025; Easter 2026 = Apr 5 2026, so
  Septuagesima = Feb 1, Ash Wednesday = Feb 18, Pentecost = May 24, and
  Holy Trinity = May 31 2026. Advent 1 2026 = Nov 29 2026.
  """

  BOUNDARIES = [
      (D(2025, 11, 29), "Trinity Season"),  # eve of Advent 1
      (D(2025, 11, 30), "Advent"),
      (D(2025, 12, 24), "Advent"),
      (D(2025, 12, 25), "Christmas"),
      (D(2026, 1, 5), "Christmas"),
      (D(2026, 1, 6), "Epiphany"),
      (D(2026, 1, 31), "Epiphany"),
      (D(2026, 2, 1), "Pre-Lent"),  # Septuagesima
      (D(2026, 2, 17), "Pre-Lent"),  # Shrove Tuesday
      (D(2026, 2, 18), "Lent"),  # Ash Wednesday
      (D(2026, 4, 4), "Lent"),  # Holy Saturday
      (D(2026, 4, 5), "Easter"),
      (D(2026, 5, 23), "Easter"),
      (D(2026, 5, 24), "Pentecost"),
      (D(2026, 5, 30), "Pentecost"),
      (D(2026, 5, 31), "Trinity Season"),  # Holy Trinity
      (D(2026, 11, 28), "Trinity Season"),
      (D(2026, 11, 29), "Advent"),
  ]

  def test_season_boundaries(self):
    for day, expected in self.BOUNDARIES:
      self.assertEqual(liturgy.get_church_season(day), expected, day)

  def test_every_day_has_a_season_in_wheel_order(self):
    # Sweep a full church year: every day maps to a known season, and the
    # seasons appear in CHURCH_SEASONS order (starting at Advent).
    start = liturgy.get_church_year(2025).calculate_advent1(2025)
    end = liturgy.get_church_year(2026).calculate_advent1(2026)
    seen = []
    day = start
    while day < end:
      season = liturgy.get_church_season(day)
      self.assertIn(season, liturgy.CHURCH_SEASONS, day)
      if not seen or seen[-1] != season:
        seen.append(season)
      day += datetime.timedelta(days=1)
    self.assertEqual(seen, list(liturgy.CHURCH_SEASONS))


class MidWeekKeyTests(unittest.TestCase):

  def setUp(self):
    self.cy = liturgy.get_church_year(2026)
    self.easter = self.cy.easter_date

  def test_ash_wednesday_anchor(self):
    self.assertEqual(
        self.cy.get_mid_week_lectionary_key(self.cy.ash_wednesday),
        "ash_wednesday",
    )

  def test_christmas_day_anchor(self):
    self.assertEqual(
        self.cy.get_mid_week_lectionary_key(D(2026, 12, 25)), "christmas_day"
    )

  def test_easter_day_anchor(self):
    self.assertEqual(
        self.cy.get_mid_week_lectionary_key(self.easter), "easter_day"
    )

  def test_pentecost_anchor(self):
    pentecost = self.easter + datetime.timedelta(days=49)
    self.assertEqual(self.cy.get_mid_week_lectionary_key(pentecost), "pentecost")

  def test_trinity_anchor(self):
    trinity = self.easter + datetime.timedelta(days=56)
    self.assertEqual(self.cy.get_mid_week_lectionary_key(trinity), "trinity")


if __name__ == "__main__":
  unittest.main()
