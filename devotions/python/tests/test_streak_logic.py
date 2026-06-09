"""Unit tests for streak_logic (grace days + streak math).

streak_logic imports only the standard library, so this suite runs without the
google-cloud / protobuf stack (which currently can't import under Python 3.14).
Run from the repo root:

    python -m unittest discover -s devotions/python/tests -t devotions/python
"""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streak_logic

D = datetime.date


def days_ago(today, n):
  return today - datetime.timedelta(days=n)


class ParseYmdTests(unittest.TestCase):

  def test_valid(self):
    self.assertEqual(streak_logic.parse_ymd("2026-06-08"), D(2026, 6, 8))

  def test_empty_and_none(self):
    self.assertIsNone(streak_logic.parse_ymd(""))
    self.assertIsNone(streak_logic.parse_ymd(None))

  def test_garbage(self):
    self.assertIsNone(streak_logic.parse_ymd("not-a-date"))
    self.assertIsNone(streak_logic.parse_ymd("2026/06/08"))


class GraceAvailableTests(unittest.TestCase):

  def setUp(self):
    self.today = D(2026, 6, 8)

  def test_never_used_is_available(self):
    self.assertTrue(streak_logic.grace_available(None, self.today))

  def test_used_today_not_available(self):
    self.assertFalse(streak_logic.grace_available(self.today, self.today))

  def test_within_cooldown_not_available(self):
    self.assertFalse(
        streak_logic.grace_available(days_ago(self.today, 6), self.today)
    )

  def test_exactly_cooldown_available(self):
    self.assertTrue(
        streak_logic.grace_available(days_ago(self.today, 7), self.today)
    )

  def test_long_past_available(self):
    self.assertTrue(
        streak_logic.grace_available(days_ago(self.today, 30), self.today)
    )


class IsStreakActiveTests(unittest.TestCase):

  def setUp(self):
    self.today = D(2026, 6, 8)

  def test_none_is_inactive(self):
    self.assertFalse(streak_logic.is_streak_active(None, self.today, True))

  def test_today_active(self):
    self.assertTrue(
        streak_logic.is_streak_active(self.today, self.today, False)
    )

  def test_yesterday_active(self):
    self.assertTrue(
        streak_logic.is_streak_active(days_ago(self.today, 1), self.today, False)
    )

  def test_two_days_active_only_with_grace(self):
    two_ago = days_ago(self.today, 2)
    self.assertTrue(streak_logic.is_streak_active(two_ago, self.today, True))
    self.assertFalse(streak_logic.is_streak_active(two_ago, self.today, False))

  def test_three_days_inactive_even_with_grace(self):
    self.assertFalse(
        streak_logic.is_streak_active(days_ago(self.today, 3), self.today, True)
    )

  def test_future_date_not_punished(self):
    future = self.today + datetime.timedelta(days=1)
    self.assertTrue(streak_logic.is_streak_active(future, self.today, False))


class EvaluateCompletionTests(unittest.TestCase):

  def setUp(self):
    self.today = D(2026, 6, 8)

  def test_already_done_today(self):
    out = streak_logic.evaluate_completion(self.today, self.today, 5, True)
    self.assertEqual(out["new_streak"], 5)
    self.assertFalse(out["streak_updated"])
    self.assertTrue(out["already_done_today"])
    self.assertFalse(out["grace_used"])

  def test_prayed_yesterday_increments(self):
    out = streak_logic.evaluate_completion(
        days_ago(self.today, 1), self.today, 5, True
    )
    self.assertEqual(out["new_streak"], 6)
    self.assertTrue(out["streak_updated"])
    self.assertFalse(out["grace_used"])

  def test_missed_one_day_with_grace_continues(self):
    out = streak_logic.evaluate_completion(
        days_ago(self.today, 2), self.today, 5, True
    )
    self.assertEqual(out["new_streak"], 6)
    self.assertTrue(out["streak_updated"])
    self.assertTrue(out["grace_used"])

  def test_missed_one_day_without_grace_resets(self):
    out = streak_logic.evaluate_completion(
        days_ago(self.today, 2), self.today, 5, False
    )
    self.assertEqual(out["new_streak"], 1)
    self.assertTrue(out["streak_updated"])
    self.assertFalse(out["grace_used"])

  def test_missed_two_days_resets_even_with_grace(self):
    out = streak_logic.evaluate_completion(
        days_ago(self.today, 3), self.today, 5, True
    )
    self.assertEqual(out["new_streak"], 1)
    self.assertFalse(out["grace_used"])

  def test_first_ever_starts_at_one(self):
    out = streak_logic.evaluate_completion(None, self.today, 0, True)
    self.assertEqual(out["new_streak"], 1)
    self.assertFalse(out["grace_used"])


class GraceCooldownScenarioTests(unittest.TestCase):
  """Grace rescues at most one missed day per cooldown window."""

  def test_cannot_use_grace_twice_within_cooldown(self):
    last_prayer = D(2026, 6, 1)
    last_grace = None

    # Returns June 3 after missing June 2 -> grace is available and used.
    today = D(2026, 6, 3)
    grace_ok = streak_logic.grace_available(last_grace, today)
    self.assertTrue(grace_ok)
    first = streak_logic.evaluate_completion(last_prayer, today, 3, grace_ok)
    self.assertTrue(first["grace_used"])
    self.assertEqual(first["new_streak"], 4)
    last_prayer, last_grace = today, today  # grace consumed today

    # Returns June 5 after missing June 4 -> only 2 days since grace -> denied,
    # so the streak resets instead of being rescued again.
    today = D(2026, 6, 5)
    grace_ok = streak_logic.grace_available(last_grace, today)
    self.assertFalse(grace_ok)
    second = streak_logic.evaluate_completion(
        last_prayer, today, first["new_streak"], grace_ok
    )
    self.assertFalse(second["grace_used"])
    self.assertEqual(second["new_streak"], 1)


if __name__ == "__main__":
  unittest.main()
