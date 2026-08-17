"""Unit tests for reading_plan_logic (plan day progression).

reading_plan_logic imports only the standard library, so this suite runs
without the google-cloud / protobuf stack. Run from the repo root:

    python -m unittest discover -s devotions/python/tests -t devotions/python
"""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import reading_plan_logic


class ParseVisitDateTests(unittest.TestCase):
  """Both stored last-visit formats parse; garbage returns None."""

  def test_zero_padded_server_format(self):
    self.assertEqual(
        reading_plan_logic.parse_visit_date("2026-08-17"),
        datetime.date(2026, 8, 17),
    )

  def test_unpadded_javascript_format(self):
    # The pages' getTodayDateString() writes e.g. "2026-8-7".
    self.assertEqual(
        reading_plan_logic.parse_visit_date("2026-8-7"),
        datetime.date(2026, 8, 7),
    )

  def test_bad_inputs_return_none(self):
    for bad in (None, "", "yesterday", "2026-13-40", "2026-08", 20260817):
      self.assertIsNone(reading_plan_logic.parse_visit_date(bad), bad)


class EffectiveCurrentDayTests(unittest.TestCase):
  """The saved day only advances once read, and only on a later day."""

  TODAY = datetime.date(2026, 8, 17)

  def test_same_day_stays_even_if_completed(self):
    self.assertEqual(
        reading_plan_logic.effective_current_day(
            10, "2026-08-17", [10], self.TODAY
        ),
        10,
    )

  def test_new_day_advances_completed_day(self):
    self.assertEqual(
        reading_plan_logic.effective_current_day(
            10, "2026-08-16", [10], self.TODAY
        ),
        11,
    )

  def test_new_day_holds_uncompleted_day(self):
    self.assertEqual(
        reading_plan_logic.effective_current_day(
            10, "2026-08-16", [1, 2, 9], self.TODAY
        ),
        10,
    )

  def test_advances_at_most_one_day(self):
    # A week away still only steps forward once: the next day itself
    # hasn't been read yet.
    self.assertEqual(
        reading_plan_logic.effective_current_day(
            10, "2026-08-01", [10], self.TODAY
        ),
        11,
    )

  def test_wraps_from_last_day_to_first(self):
    self.assertEqual(
        reading_plan_logic.effective_current_day(
            365, "2026-08-16", [365], self.TODAY
        ),
        1,
    )

  def test_respects_num_days(self):
    self.assertEqual(
        reading_plan_logic.effective_current_day(
            75, "2026-08-16", [75], self.TODAY, num_days=75
        ),
        1,
    )

  def test_no_completed_days(self):
    for empty in (None, [], ()):
      self.assertEqual(
          reading_plan_logic.effective_current_day(
              10, "2026-08-16", empty, self.TODAY
          ),
          10,
      )

  def test_unparseable_last_visit_holds_day(self):
    self.assertEqual(
        reading_plan_logic.effective_current_day(
            10, "not-a-date", [10], self.TODAY
        ),
        10,
    )

  def test_out_of_range_saved_day_clamped(self):
    self.assertEqual(
        reading_plan_logic.effective_current_day(0, None, [], self.TODAY), 1
    )
    self.assertEqual(
        reading_plan_logic.effective_current_day(400, None, [], self.TODAY),
        365,
    )

  def test_unusable_saved_day_returns_none(self):
    for bad in (None, "abc", True, False):
      self.assertIsNone(
          reading_plan_logic.effective_current_day(
              bad, "2026-08-16", [1], self.TODAY
          ),
          bad,
      )

  def test_numeric_string_saved_day_accepted(self):
    # Older progress docs saved via JSON may hold the day as a string.
    self.assertEqual(
        reading_plan_logic.effective_current_day(
            "10", "2026-08-16", [10], self.TODAY
        ),
        11,
    )


if __name__ == "__main__":
  unittest.main()
