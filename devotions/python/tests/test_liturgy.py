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
