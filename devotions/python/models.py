"""Data models for the application."""

import datetime
import flask_login
import pytz
import utils


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
      streak_count=0,
      best_streak_count=0,
      last_prayer_date=None,
      achievements=None,
      completed_devotions=None,
      bible_streak_count=0,
      best_bible_streak_count=0,
      last_bible_reading_date=None,
      completed_bible_days=None,
      prayed_request_ids=None,
      memorized_verses=None,
      completed_catechism_sections=None,
      created_at=None,
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
    self.achievements = achievements or []
    self.completed_devotions = completed_devotions or {}
    self.completed_bible_days = completed_bible_days or []
    self.prayed_request_ids = prayed_request_ids or []
    self.memorized_verses = memorized_verses or []
    self.completed_catechism_sections = completed_catechism_sections or []
    self.created_at = created_at

    # Calculate effective streaks based on current date
    tz_str = self.timezone or "America/New_York"
    try:
      tz = pytz.timezone(tz_str)
    except pytz.UnknownTimeZoneError:
      tz = pytz.timezone("America/New_York")

    now_date = datetime.datetime.now(tz).date()

    # Capture best streak before potential reset (for legacy data)
    self.best_streak_count = max(best_streak_count, streak_count)
    self.best_bible_streak_count = max(
        best_bible_streak_count, bible_streak_count
    )

    # Prayer Streak Logic
    if last_prayer_date:
      try:
        last_date = datetime.datetime.strptime(
            last_prayer_date, "%Y-%m-%d"
        ).date()
        # If last prayer was before yesterday (gap > 1 day), streak is broken
        if last_date < now_date - datetime.timedelta(days=1):
          streak_count = 0
      except ValueError:
        pass
    else:
      streak_count = 0

    self.streak_count = streak_count
    self.last_prayer_date = last_prayer_date

    # Bible Streak Logic
    if last_bible_reading_date:
      try:
        last_bible = datetime.datetime.strptime(
            last_bible_reading_date, "%Y-%m-%d"
        ).date()
        if last_bible < now_date - datetime.timedelta(days=1):
          bible_streak_count = 0
      except ValueError:
        pass
    else:
      bible_streak_count = 0

    self.bible_streak_count = bible_streak_count
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
          streak_count=data.get("streak_count", 0),
          best_streak_count=data.get("best_streak_count", 0),
          last_prayer_date=data.get("last_prayer_date"),
          achievements=data.get("achievements", []),
          completed_devotions=data.get("completed_devotions", {}),
          bible_streak_count=data.get("bible_streak_count", 0),
          best_bible_streak_count=data.get("best_bible_streak_count", 0),
          last_bible_reading_date=data.get("last_bible_reading_date"),
          completed_bible_days=data.get("completed_bible_days", []),
          prayed_request_ids=data.get("prayed_request_ids", []),
          memorized_verses=data.get("memorized_verses", []),
          completed_catechism_sections=data.get(
              "completed_catechism_sections", []
          ),
          created_at=data.get("created_at"),
      )
    return None
