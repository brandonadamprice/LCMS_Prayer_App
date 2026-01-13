"""Data models for the application."""

import flask_login
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
        "prayer_reminders": {"push": True, "sms": False},
        "prayed_for_me": {"push": True, "sms": False},
    }
    self.password_hash = password_hash
    self.google_id = google_id
    self.timezone = timezone

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
      )
    return None
