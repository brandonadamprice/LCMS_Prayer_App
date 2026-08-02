"""Pure signup-analytics math for the admin traffic page.

Deliberately free of Flask/Firestore imports (see CLAUDE.md) so the window
counts and weekly bucketing stay unit-testable. The Firestore side lives in
routes/misc.py, which streams user docs and hands the created_at values here.
"""

import datetime


def as_aware_utc(value):
  """Coerces a stored created_at value to an aware UTC datetime.

  Firestore returns aware datetimes, but older docs (and tests) may carry
  naive ones; naive values are treated as UTC. Anything that is not a
  datetime (None, strings from bad writes) maps to None so callers can
  skip legacy users that predate created_at tracking.
  """
  if not isinstance(value, datetime.datetime):
    return None
  if value.tzinfo is None:
    return value.replace(tzinfo=datetime.timezone.utc)
  return value.astimezone(datetime.timezone.utc)


def summarize_signups(created_ats, now, weeks=8):
  """Buckets signup timestamps into recency windows and a weekly series.

  Args:
    created_ats: iterable of created_at values; entries that are not
      datetimes are ignored (legacy users predate created_at tracking).
    now: aware datetime to measure windows back from.
    weeks: number of trailing 7-day buckets in the chart series.

  Returns:
    Dict with:
      total_tracked: users that have a usable created_at at all.
      last_7_days / last_30_days: signup counts in those trailing windows.
      weekly: list of {"start": date, "count": int}, oldest bucket first,
        each covering the 7 days beginning at "start" (buckets are rolling
        7-day windows ending at `now`, not calendar weeks).
  """
  signups = sorted(
      ts for ts in (as_aware_utc(v) for v in created_ats) if ts is not None
  )

  last_7 = now - datetime.timedelta(days=7)
  last_30 = now - datetime.timedelta(days=30)
  series_start = now - datetime.timedelta(days=7 * weeks)

  weekly_counts = [0] * weeks
  count_7 = 0
  count_30 = 0
  for ts in signups:
    if ts > now:
      # Clock skew / bad data; count it in the newest bucket rather than
      # crashing or silently dropping a real user.
      ts = now
    if ts > last_7:
      count_7 += 1
    if ts > last_30:
      count_30 += 1
    if ts > series_start:
      index = int((ts - series_start).total_seconds() // (7 * 86400))
      weekly_counts[min(index, weeks - 1)] += 1

  weekly = [
      {
          "start": (series_start + datetime.timedelta(days=7 * i)).date(),
          "count": weekly_counts[i],
      }
      for i in range(weeks)
  ]

  return {
      "total_tracked": len(signups),
      "last_7_days": count_7,
      "last_30_days": count_30,
      "weekly": weekly,
  }
