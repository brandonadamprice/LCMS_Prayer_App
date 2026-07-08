"""Tests for pure reminder scheduling math, including DST boundaries.

Uses pytz (already a runtime dependency, import-light -- no Firestore/
protobuf stack) because production passes pytz timezones in and pytz's
localize() semantics are exactly what the DST regression tests must pin.
"""

import datetime
import unittest

import pytz

import reminder_logic

UTC = datetime.timezone.utc
EASTERN = pytz.timezone("America/New_York")
# US DST in 2026: begins Mar 8 (spring forward), ends Nov 1 (fall back).


def eastern(y, mo, d, h, mi):
  return EASTERN.localize(datetime.datetime(y, mo, d, h, mi))


class NextRunUtcTest(unittest.TestCase):

  def test_later_today(self):
    # 08:00 EST; 09:30 reminder is later today. EST is UTC-5.
    now = eastern(2026, 1, 15, 8, 0)
    result = reminder_logic.next_run_utc("09:30", EASTERN, now)
    self.assertEqual(
        result, datetime.datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    )

  def test_already_passed_rolls_to_tomorrow(self):
    now = eastern(2026, 1, 15, 10, 0)
    result = reminder_logic.next_run_utc("09:30", EASTERN, now)
    self.assertEqual(
        result, datetime.datetime(2026, 1, 16, 14, 30, tzinfo=UTC)
    )

  def test_exactly_now_rolls_to_tomorrow(self):
    now = eastern(2026, 1, 15, 9, 30)
    result = reminder_logic.next_run_utc("09:30", EASTERN, now)
    self.assertEqual(
        result, datetime.datetime(2026, 1, 16, 14, 30, tzinfo=UTC)
    )

  def test_midnight_reminder(self):
    now = eastern(2026, 1, 15, 8, 0)
    result = reminder_logic.next_run_utc("00:00", EASTERN, now)
    self.assertEqual(
        result, datetime.datetime(2026, 1, 16, 5, 0, tzinfo=UTC)
    )

  def test_fall_back_fires_at_correct_local_time(self):
    """The historical bug: offsets must not be carried across fall-back.

    Computed at 23:00 EDT (UTC-4) the night before DST ends, a 06:00
    reminder lands after the switch to EST (UTC-5), so the right answer is
    11:00 UTC. The old arithmetic kept the EDT offset and produced 10:00
    UTC = 05:00 local, an hour early.
    """
    now = eastern(2026, 10, 31, 23, 0)
    self.assertEqual(now.utcoffset(), datetime.timedelta(hours=-4))  # EDT
    result = reminder_logic.next_run_utc("06:00", EASTERN, now)
    self.assertEqual(
        result, datetime.datetime(2026, 11, 1, 11, 0, tzinfo=UTC)
    )

  def test_spring_forward_nonexistent_time_does_not_crash(self):
    """02:30 does not exist on 2026-03-08; policy maps it via EST.

    pytz localize(is_dst=False) tags the gap time as EST (UTC-5), i.e.
    07:30 UTC, which is 03:30 EDT -- the reminder fires an hour "late" on
    the wall clock that morning rather than crashing or firing early.
    """
    now = eastern(2026, 3, 7, 23, 0)
    self.assertEqual(now.utcoffset(), datetime.timedelta(hours=-5))  # EST
    result = reminder_logic.next_run_utc("02:30", EASTERN, now)
    self.assertEqual(
        result, datetime.datetime(2026, 3, 8, 7, 30, tzinfo=UTC)
    )

  def test_ambiguous_fall_back_time_resolves_to_standard(self):
    """01:30 occurs twice on 2026-11-01; policy picks the EST occurrence."""
    now = eastern(2026, 10, 31, 23, 0)
    result = reminder_logic.next_run_utc("01:30", EASTERN, now)
    self.assertEqual(
        result, datetime.datetime(2026, 11, 1, 6, 30, tzinfo=UTC)
    )

  def test_now_in_different_zone_than_tz(self):
    """`now` may be UTC (as the cron job sees it); local math still holds."""
    now = datetime.datetime(2026, 1, 15, 13, 0, tzinfo=UTC)  # 08:00 EST
    result = reminder_logic.next_run_utc("09:30", EASTERN, now)
    self.assertEqual(
        result, datetime.datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    )

  def test_stdlib_fixed_offset_timezone_supported(self):
    tz = datetime.timezone(datetime.timedelta(hours=12))  # e.g. NZ standard
    now = datetime.datetime(2026, 1, 15, 8, 0, tzinfo=tz)
    result = reminder_logic.next_run_utc("09:30", tz, now)
    self.assertEqual(
        result, datetime.datetime(2026, 1, 14, 21, 30, tzinfo=UTC)
    )


if __name__ == "__main__":
  unittest.main()
