"""Tests for the pure signup-analytics math."""

import datetime
import unittest

import signup_analytics_logic


UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def days_ago(days, hours=0):
  return NOW - datetime.timedelta(days=days, hours=hours)


class AsAwareUtcTest(unittest.TestCase):

  def test_none_and_non_datetime_map_to_none(self):
    self.assertIsNone(signup_analytics_logic.as_aware_utc(None))
    self.assertIsNone(signup_analytics_logic.as_aware_utc("2026-01-01"))
    self.assertIsNone(signup_analytics_logic.as_aware_utc(1234567890))

  def test_naive_treated_as_utc(self):
    naive = datetime.datetime(2026, 8, 1, 6, 30)
    aware = signup_analytics_logic.as_aware_utc(naive)
    self.assertEqual(aware.tzinfo, UTC)
    self.assertEqual(aware.hour, 6)

  def test_aware_converted_to_utc(self):
    est = datetime.timezone(datetime.timedelta(hours=-5))
    value = datetime.datetime(2026, 8, 1, 6, 30, tzinfo=est)
    aware = signup_analytics_logic.as_aware_utc(value)
    self.assertEqual(aware.tzinfo, UTC)
    self.assertEqual(aware.hour, 11)


class SummarizeSignupsTest(unittest.TestCase):

  def test_empty_input(self):
    summary = signup_analytics_logic.summarize_signups([], NOW)
    self.assertEqual(summary["total_tracked"], 0)
    self.assertEqual(summary["last_7_days"], 0)
    self.assertEqual(summary["last_30_days"], 0)
    self.assertEqual(len(summary["weekly"]), 8)
    self.assertTrue(all(w["count"] == 0 for w in summary["weekly"]))

  def test_window_counts(self):
    created = [
        days_ago(1),    # in 7d and 30d
        days_ago(6),    # in 7d and 30d
        days_ago(8),    # in 30d only
        days_ago(29),   # in 30d only
        days_ago(31),   # in neither
        days_ago(400),  # ancient
    ]
    summary = signup_analytics_logic.summarize_signups(created, NOW)
    self.assertEqual(summary["total_tracked"], 6)
    self.assertEqual(summary["last_7_days"], 2)
    self.assertEqual(summary["last_30_days"], 4)

  def test_boundary_exactly_seven_days_is_excluded(self):
    # Windows are (now - N days, now]: an exact 7-days-ago timestamp falls
    # outside the 7-day window but inside the 30-day one.
    summary = signup_analytics_logic.summarize_signups([days_ago(7)], NOW)
    self.assertEqual(summary["last_7_days"], 0)
    self.assertEqual(summary["last_30_days"], 1)

  def test_legacy_users_without_created_at_are_ignored(self):
    created = [None, "not a date", days_ago(2)]
    summary = signup_analytics_logic.summarize_signups(created, NOW)
    self.assertEqual(summary["total_tracked"], 1)
    self.assertEqual(summary["last_7_days"], 1)

  def test_weekly_buckets(self):
    created = [
        days_ago(0, hours=1),  # newest bucket
        days_ago(3),           # newest bucket
        days_ago(10),          # second-newest bucket
        days_ago(55),          # oldest bucket (days 49-56 ago)
        days_ago(56, hours=1), # just outside the 8-week series
    ]
    summary = signup_analytics_logic.summarize_signups(created, NOW)
    counts = [w["count"] for w in summary["weekly"]]
    self.assertEqual(counts, [1, 0, 0, 0, 0, 0, 1, 2])
    # Buckets are contiguous 7-day spans, oldest first.
    starts = [w["start"] for w in summary["weekly"]]
    self.assertEqual(starts[0], (NOW - datetime.timedelta(days=56)).date())
    for earlier, later in zip(starts, starts[1:]):
      self.assertEqual(later - earlier, datetime.timedelta(days=7))

  def test_future_timestamp_counts_in_newest_bucket(self):
    summary = signup_analytics_logic.summarize_signups(
        [NOW + datetime.timedelta(hours=2)], NOW
    )
    self.assertEqual(summary["last_7_days"], 1)
    self.assertEqual(summary["weekly"][-1]["count"], 1)

  def test_custom_week_count(self):
    summary = signup_analytics_logic.summarize_signups(
        [days_ago(20)], NOW, weeks=4
    )
    self.assertEqual(len(summary["weekly"]), 4)
    self.assertEqual(sum(w["count"] for w in summary["weekly"]), 1)


if __name__ == "__main__":
  unittest.main()
