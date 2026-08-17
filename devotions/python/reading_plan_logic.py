"""Pure, dependency-free reading-plan day-progression math.

A saved plan day (Bible in a Year, Psalter) only rolls forward to the next
day once (a) a new calendar day has arrived since the last visit and (b) the
saved day was actually marked as read. This mirrors the client-side logic in
bible_in_a_year.html / psalter.html so pages rendered server-side (the office
devotions' Bible in a Year reading) agree with the plan pages.

Deliberately free of firebase/google-cloud imports so it stays unit-testable
(see tests/test_reading_plan_logic.py).
"""

import datetime


def parse_visit_date(last_visit_str):
  """Parses a stored last-visit string into a date, or None if unparseable.

  Accepts both the zero-padded "%Y-%m-%d" written by the server and the
  unpadded "YYYY-M-D" written by the pages' JavaScript getTodayDateString().
  """
  if not last_visit_str or not isinstance(last_visit_str, str):
    return None
  parts = last_visit_str.split("-")
  if len(parts) != 3:
    return None
  try:
    year, month, day = (int(p) for p in parts)
    return datetime.date(year, month, day)
  except ValueError:
    return None


def effective_current_day(
    saved_day, last_visit_str, completed_days, today, num_days=365
):
  """Returns the day the user should be on, advancing past a finished day.

  The saved day advances by exactly one (wrapping from num_days back to 1)
  when today is a later calendar day than the last visit AND the saved day is
  in completed_days; otherwise the saved day is returned unchanged (clamped
  into 1..num_days). Returns None when saved_day isn't usable, so callers can
  fall back to their own default.
  """
  if isinstance(saved_day, bool):
    return None
  try:
    day = int(saved_day)
  except (TypeError, ValueError):
    return None
  day = max(1, min(day, num_days))

  last_visit = parse_visit_date(last_visit_str)
  if (
      last_visit is not None
      and today > last_visit
      and day in (completed_days or ())
  ):
    day = day % num_days + 1
  return day
