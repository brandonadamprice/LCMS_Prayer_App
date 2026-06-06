"""Regression tests for utils.resolve_timezone.

resolve_timezone must always return a usable tzinfo: the requested zone when it
is valid, and the app default (US Eastern) when the name is empty, None, or
unrecognized. These cases guard against a regression where an unset or bad user
timezone could raise instead of quietly falling back to Eastern.

Run from the devotions/python directory so the app's flat imports resolve:
    ../.venv/Scripts/python.exe -m unittest test_utils
"""

import types
import unittest

import utils


class ResolveTimezoneTest(unittest.TestCase):

  def test_valid_timezone_is_returned(self):
    result = utils.resolve_timezone("America/Chicago")
    self.assertEqual(result.zone, "America/Chicago")

  def test_default_constant_is_eastern(self):
    self.assertEqual(utils.EASTERN_TZ.zone, "America/New_York")

  def test_empty_string_falls_back_to_eastern(self):
    self.assertIs(utils.resolve_timezone(""), utils.EASTERN_TZ)

  def test_none_falls_back_to_eastern(self):
    self.assertIs(utils.resolve_timezone(None), utils.EASTERN_TZ)

  def test_unknown_timezone_falls_back_to_eastern(self):
    self.assertIs(utils.resolve_timezone("Not/AZone"), utils.EASTERN_TZ)


class NowForUserTest(unittest.TestCase):
  """now_for_user must localize to the user's timezone and fall back to Eastern
  for anonymous users or users with no/invalid timezone, matching the behavior
  the routes and template context processor previously inlined."""

  def test_uses_users_timezone(self):
    user = types.SimpleNamespace(timezone="America/Chicago")
    self.assertEqual(utils.now_for_user(user).tzinfo.zone, "America/Chicago")

  def test_missing_timezone_attribute_falls_back_to_eastern(self):
    # An anonymous user object has no ``timezone`` attribute at all.
    self.assertEqual(
        utils.now_for_user(object()).tzinfo.zone, "America/New_York"
    )

  def test_none_timezone_falls_back_to_eastern(self):
    user = types.SimpleNamespace(timezone=None)
    self.assertEqual(utils.now_for_user(user).tzinfo.zone, "America/New_York")

  def test_empty_timezone_falls_back_to_eastern(self):
    user = types.SimpleNamespace(timezone="")
    self.assertEqual(utils.now_for_user(user).tzinfo.zone, "America/New_York")

  def test_unknown_timezone_falls_back_to_eastern(self):
    user = types.SimpleNamespace(timezone="Not/AZone")
    self.assertEqual(utils.now_for_user(user).tzinfo.zone, "America/New_York")


if __name__ == "__main__":
  unittest.main()
