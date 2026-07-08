"""Pure, dependency-free reminder scheduling math.

No Firestore/Flask/pytz imports so it stays unit-testable like
streak_logic.py. Timezone objects are duck-typed: pytz timezones (which
require .localize() for correct DST handling) and stdlib zoneinfo/tzinfo
both work. The Firestore side lives in services/reminders.py.
"""

import datetime


def _localize(tz, naive):
  """Attaches tz to a naive wall-clock datetime, DST-correctly.

  pytz timezones must go through localize() -- naive.replace(tzinfo=pytz_tz)
  silently picks the zone's oldest historical offset (LMT). For a
  nonexistent wall-clock time (spring-forward gap), pytz's default
  is_dst=False maps it onto standard time, which lands one hour later in
  real terms -- an acceptable policy for reminders. Ambiguous times
  (fall-back hour) resolve to the standard-time (second) occurrence.
  """
  if hasattr(tz, "localize"):
    return tz.localize(naive)
  return naive.replace(tzinfo=tz)


def next_run_utc(time_str, tz, now):
  """Next occurrence of wall-clock "HH:MM" in tz, as an aware UTC datetime.

  `now` must be timezone-aware. The candidate is built as a naive wall-clock
  time on the user's local calendar day and then localized -- NOT derived by
  arithmetic on `now`, which would carry `now`'s UTC offset across a DST
  boundary (the historical bug: a 06:00 reminder computed the night before
  a fall-back transition fired at 05:00 local).
  """
  hour, minute = map(int, time_str.split(":"))
  local_now = now.astimezone(tz)
  candidate_naive = datetime.datetime(
      local_now.year, local_now.month, local_now.day, hour, minute
  )
  candidate = _localize(tz, candidate_naive)
  if candidate <= now:
    candidate = _localize(
        tz, candidate_naive + datetime.timedelta(days=1)
    )
  return candidate.astimezone(datetime.timezone.utc)
