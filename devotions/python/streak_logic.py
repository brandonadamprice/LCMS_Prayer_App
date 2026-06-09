"""Pure, dependency-free streak math (grace days included).

This module deliberately imports only the standard library so it can be unit
tested without the ``google-cloud`` / ``protobuf`` stack, which currently fails
to import under Python 3.14. ``models.py`` and ``services/users.py`` call into
these helpers for all streak decisions; keep this file free of Firestore,
Flask, or other heavy imports.

Grace day
---------
A streak should not die because a user misses a single day. When the user
returns after exactly one fully-missed day, a "grace day" can bridge the gap
and keep the streak going. Grace is rate-limited by a cooldown (see
``DEFAULT_GRACE_COOLDOWN_DAYS``) so it forgives the occasional slip without
letting an every-other-day pattern keep a streak alive indefinitely.
"""

import datetime

# A grace day can be used at most once per this many days. With the default of
# 7, a user can miss at most one day per week and still hold their streak.
DEFAULT_GRACE_COOLDOWN_DAYS = 7


def parse_ymd(date_str):
  """Parses a 'YYYY-MM-DD' string to a date, or returns None if it can't."""
  if not date_str:
    return None
  try:
    return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
  except (ValueError, TypeError):
    return None


def grace_available(
    last_grace_date, today, cooldown_days=DEFAULT_GRACE_COOLDOWN_DAYS
):
  """Returns True if a grace day may be used today.

  Grace is available if it has never been used (``last_grace_date`` is None) or
  if at least ``cooldown_days`` have elapsed since it was last used.
  """
  if last_grace_date is None:
    return True
  return (today - last_grace_date).days >= cooldown_days


def is_streak_active(last_date, today, grace_ok):
  """Whether a stored streak should still count as active (for display).

  Active when the last activity was today or yesterday. If a grace day is
  available, a single fully-missed day (a two-day gap) is still considered
  active, because the user can pray today to bridge it.
  """
  if last_date is None:
    return False
  gap = (today - last_date).days
  if gap < 0:
    # Future date (timezone skew / clock change); don't punish the user.
    return True
  if gap <= 1:
    return True
  if gap == 2 and grace_ok:
    return True
  return False


def evaluate_completion(last_date, today, current_streak, grace_ok):
  """Computes the streak outcome when an activity is completed today.

  Returns a dict with:
    new_streak:         the streak count after this completion
    streak_updated:     whether the stored count changes today
    already_done_today: the activity was already completed earlier today
    grace_used:         a grace day was consumed to bridge a missed day
  """
  if last_date == today:
    return {
        "new_streak": current_streak,
        "streak_updated": False,
        "already_done_today": True,
        "grace_used": False,
    }

  yesterday = today - datetime.timedelta(days=1)
  if last_date == yesterday:
    return {
        "new_streak": current_streak + 1,
        "streak_updated": True,
        "already_done_today": False,
        "grace_used": False,
    }

  # Exactly one fully-missed day, and grace is available to cover it.
  if (
      last_date is not None
      and (today - last_date).days == 2
      and grace_ok
  ):
    return {
        "new_streak": current_streak + 1,
        "streak_updated": True,
        "already_done_today": False,
        "grace_used": True,
    }

  # First-ever activity, or a gap too large for grace: start over at 1.
  return {
      "new_streak": 1,
      "streak_updated": True,
      "already_done_today": False,
      "grace_used": False,
  }
