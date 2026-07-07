"""Data models for the application."""

import datetime
import flask_login
import streak_logic
import utils


def compute_active_streak(
    streak_count, last_activity_date, timezone_str, last_grace_date=None
):
  """Returns the streak count if it is still active, otherwise 0.

  A streak is "active" if the last activity happened today or yesterday in the
  user's timezone. If a grace day is available, a single fully-missed day still
  counts as active, since the user can complete an activity today to bridge it.
  A missing/empty date means there is no active streak; an unparseable date
  leaves the stored count untouched.
  """
  if not last_activity_date:
    return 0
  tz = utils.resolve_timezone(timezone_str)
  now_date = datetime.datetime.now(tz).date()
  last_date = streak_logic.parse_ymd(last_activity_date)
  if last_date is None:
    return streak_count
  grace_ok = streak_logic.grace_available(
      streak_logic.parse_ymd(last_grace_date), now_date
  )
  if streak_logic.is_streak_active(last_date, now_date, grace_ok):
    return streak_count
  return 0


class User(flask_login.UserMixin):
  """User class for Flask-Login."""

  def __init__(
      self,
      user_id,
      email=None,
      name=None,
      profile_pic=None,
      dark_mode=None,
      font_size_level=None,
      favorites=None,
      fcm_tokens=None,
      google_profile_pic=None,
      selected_pic_source=None,
      phone_number=None,
      notification_preferences=None,
      password_hash=None,
      google_id=None,
      timezone=None,
      background_art=True,
      hide_catechism=False,
      streak_count=0,
      best_streak_count=0,
      last_prayer_date=None,
      last_prayer_grace_date=None,
      achievements=None,
      completed_devotions=None,
      bible_streak_count=0,
      best_bible_streak_count=0,
      last_bible_reading_date=None,
      last_bible_grace_date=None,
      completed_bible_days=None,
      prayed_request_ids=None,
      memorized_verses=None,
      completed_catechism_sections=None,
      reading_preferences=None,
      psalm_preferences=None,
      created_at=None,
      last_seen=None,
      bia_progress=None,
  ):
    self.id = user_id
    self.email = email
    self.name = name
    self.profile_pic = profile_pic
    self.dark_mode = dark_mode
    self.font_size_level = font_size_level
    self.favorites = favorites or []
    self.fcm_tokens = fcm_tokens or []
    self.google_profile_pic = google_profile_pic
    self.selected_pic_source = selected_pic_source
    self.phone_number = phone_number
    self.notification_preferences = notification_preferences or {
        "prayer_reminders": {"push": True, "email": True, "sms": False},
        "prayed_for_me": {"push": True, "email": False, "sms": False},
        "site_messages": {"push": True, "email": True, "sms": False},
    }
    self.password_hash = password_hash
    self.google_id = google_id
    self.timezone = timezone
    self.background_art = background_art
    self.hide_catechism = hide_catechism
    self.achievements = achievements or []
    self.completed_devotions = completed_devotions or {}
    self.completed_bible_days = completed_bible_days or []
    self.prayed_request_ids = prayed_request_ids or []
    self.memorized_verses = memorized_verses or []
    self.completed_catechism_sections = completed_catechism_sections or []
    self.reading_preferences = reading_preferences or {}
    self.psalm_preferences = psalm_preferences or {}
    self.created_at = created_at
    self.last_seen = last_seen
    self.bia_progress = bia_progress or {}

    # Capture best streak before potential reset (for legacy data)
    self.best_streak_count = max(best_streak_count, streak_count)
    self.best_bible_streak_count = max(
        best_bible_streak_count, bible_streak_count
    )

    # A streak only counts if the last activity was today or yesterday in the
    # user's timezone -- or one fully-missed day when a grace day is available;
    # otherwise it has lapsed and resets to 0.
    tz_str = self.timezone or "America/New_York"
    self.last_prayer_grace_date = last_prayer_grace_date
    self.last_bible_grace_date = last_bible_grace_date
    self.streak_count = compute_active_streak(
        streak_count, last_prayer_date, tz_str, last_prayer_grace_date
    )
    self.last_prayer_date = last_prayer_date
    self.bible_streak_count = compute_active_streak(
        bible_streak_count,
        last_bible_reading_date,
        tz_str,
        last_bible_grace_date,
    )
    self.last_bible_reading_date = last_bible_reading_date

  @staticmethod
  def get(user_id):
    """Gets a user from Firestore by user_id."""
    db = utils.get_db_client()
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    if user_doc.exists:
      data = user_doc.to_dict()
      return User(
          user_id=user_id,
          email=data.get("email"),
          name=data.get("name"),
          profile_pic=data.get("profile_pic"),
          dark_mode=data.get("dark_mode"),
          font_size_level=data.get("font_size_level"),
          favorites=data.get("favorites", []),
          fcm_tokens=data.get("fcm_tokens", []),
          google_profile_pic=data.get("google_profile_pic"),
          selected_pic_source=data.get("selected_pic_source"),
          phone_number=data.get("phone_number"),
          notification_preferences=data.get("notification_preferences"),
          password_hash=data.get("password_hash"),
          google_id=data.get("google_id"),
          timezone=data.get("timezone"),
          background_art=data.get("background_art", True),
          hide_catechism=data.get("hide_catechism", False),
          streak_count=data.get("streak_count", 0),
          best_streak_count=data.get("best_streak_count", 0),
          last_prayer_date=data.get("last_prayer_date"),
          last_prayer_grace_date=data.get("last_prayer_grace_date"),
          achievements=data.get("achievements", []),
          completed_devotions=data.get("completed_devotions", {}),
          bible_streak_count=data.get("bible_streak_count", 0),
          best_bible_streak_count=data.get("best_bible_streak_count", 0),
          last_bible_reading_date=data.get("last_bible_reading_date"),
          last_bible_grace_date=data.get("last_bible_grace_date"),
          completed_bible_days=data.get("completed_bible_days", []),
          prayed_request_ids=data.get("prayed_request_ids", []),
          memorized_verses=data.get("memorized_verses", []),
          completed_catechism_sections=data.get(
              "completed_catechism_sections", []
          ),
          reading_preferences=data.get("reading_preferences", {}),
          psalm_preferences=data.get("psalm_preferences", {}),
          created_at=data.get("created_at"),
          last_seen=data.get("last_seen"),
          bia_progress=data.get("bia_progress"),
      )
    return None
