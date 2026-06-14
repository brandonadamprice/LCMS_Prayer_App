"""Unit tests for menu.get_menu_items (seasonal enable/disable logic).

menu imports only the standard library, so this suite runs without the
google-cloud / protobuf stack (which currently can't import under Python 3.14).
Run from the repo root:

    python -m unittest discover -s devotions/python/tests -t devotions/python
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import menu


def _find(items, label):
  """Returns the first submenu entry with the given label, or None."""
  for top in items:
    for sub in top.get("submenu", []):
      if sub.get("label") == label:
        return sub
  return None


class SeasonalMenuTests(unittest.TestCase):
  """Seasonal devotions are enabled only when their season flag is set."""

  def test_advent_enabled_only_in_advent(self):
    self.assertTrue(_find(menu.get_menu_items(True, False, False), "Advent")["enabled"])
    self.assertFalse(_find(menu.get_menu_items(False, False, False), "Advent")["enabled"])

  def test_new_year_enabled_only_at_new_year(self):
    self.assertTrue(_find(menu.get_menu_items(False, True, False), "New Year's")["enabled"])
    self.assertFalse(_find(menu.get_menu_items(False, False, False), "New Year's")["enabled"])

  def test_lent_enabled_only_in_lent(self):
    self.assertTrue(_find(menu.get_menu_items(False, False, True), "Lenten")["enabled"])
    self.assertFalse(_find(menu.get_menu_items(False, False, False), "Lenten")["enabled"])

  def test_seasonal_flags_are_independent(self):
    # The Advent flag must not also enable Lenten or New Year's.
    items = menu.get_menu_items(True, False, False)
    self.assertFalse(_find(items, "Lenten")["enabled"])
    self.assertFalse(_find(items, "New Year's")["enabled"])


class StaticMenuTests(unittest.TestCase):
  """Evergreen items and overall structure are stable across seasons."""

  def test_evergreen_items_always_enabled(self):
    for flags in [(False, False, False), (True, True, True)]:
      items = menu.get_menu_items(*flags)
      self.assertTrue(_find(items, "Children's")["enabled"])
      morning = _find(items, "Morning")
      self.assertIsNotNone(morning)
      self.assertTrue(morning["enabled"])

  def test_structure_shape(self):
    items = menu.get_menu_items(False, False, False)
    self.assertIsInstance(items, list)
    self.assertTrue(items)
    # Every dropdown carries a non-empty submenu.
    for top in items:
      if top.get("type") == "dropdown":
        self.assertTrue(top.get("submenu"), f"{top.get('label')} has no submenu")


if __name__ == "__main__":
  unittest.main()
