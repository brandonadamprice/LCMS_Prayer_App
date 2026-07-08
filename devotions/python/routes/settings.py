"""Settings-page and user-preference routes."""

import re
import urllib.parse

import flask
import flask_login
from google.cloud import firestore
import models
import pytz
import secrets_fetcher
from services import reminders
from services import users
import utils


def _save_user_fields(updates, use_merge=True):
  """Writes fields to the current user's doc and returns a JSON response.

  use_merge=True creates the doc if absent (set with merge); use_merge=False
  uses update(), which is required for dotted nested-field keys.
  """
  try:
    db = utils.get_db_client()
    user_ref = db.collection("users").document(flask_login.current_user.id)
    if use_merge:
      user_ref.set(updates, merge=True)
    else:
      user_ref.update(updates)
    return flask.jsonify({"success": True})
  except Exception as e:
    flask.current_app.logger.error("Failed to save user setting %s: %s", list(updates), e)
    return (
        flask.jsonify({"success": False, "error": "Database save failed"}),
        500,
    )


def register(app):
  """Registers the settings and preference routes on the app."""

  @app.route("/settings")
  def settings_route():
    """Renders the dedicated settings page."""
    if flask.request.args.get("demo") == "twilio_compliance":
      dummy_user = models.User(
          user_id="demo_user",
          email="demo@asimplewaytopray.com",
          name="Demo User",
          phone_number="+15550199999",
          notification_preferences={
              "prayer_reminders": {"push": True, "email": False, "sms": False},
              "prayed_for_me": {"push": True, "email": False, "sms": False},
          },
          timezone="America/New_York",
      )
      return flask.render_template(
          "settings.html",
          timezones=pytz.common_timezones,
          current_user=dummy_user,
      )

    return flask.render_template("settings.html", timezones=pytz.common_timezones)


  @app.route("/settings/update_profile", methods=["POST"])
  @flask_login.login_required
  def update_profile():
    """Updates user profile (name, email, phone)."""
    name = flask.request.form.get("name")
    email = flask.request.form.get("email", "").strip().lower()
    phone = flask.request.form.get("phone")

    if not name or not email:
      flask.flash("Name and Email are required.", "error")
      return flask.redirect("/settings")

    email_error = users.validate_email(email)
    if email_error:
      flask.flash(email_error, "error")
      return flask.redirect("/settings")

    # Basic phone validation/cleanup
    if phone:
      cleaned_phone = re.sub(r"[^\d+]", "", phone)
      if cleaned_phone and not cleaned_phone.startswith("+"):
        if len(cleaned_phone) == 10:
          cleaned_phone = "+1" + cleaned_phone
        else:
          cleaned_phone = "+" + cleaned_phone
      phone = cleaned_phone
    else:
      phone = None  # Explicitly set to None if empty string to clear it or handle properly

    try:
      db = utils.get_db_client()

      # Check uniqueness if email changed
      if email != flask_login.current_user.email:
        users_ref = db.collection("users")
        query = users_ref.where("email", "==", email).limit(1)
        if list(query.stream()):
          flask.flash("Email already in use.", "error")
          return flask.redirect("/settings")

      user_ref = db.collection("users").document(flask_login.current_user.id)
      update_data = {"name": name, "email": email}
      if phone is not None:
        update_data["phone_number"] = phone

      user_ref.update(update_data)
      flask.flash("Profile updated successfully.", "success")
    except Exception as e:
      app.logger.error("Failed to update profile: %s", e)
      flask.flash("An error occurred while updating profile.", "error")

    return flask.redirect("/settings")


  @app.route("/settings/save_notification_preferences", methods=["POST"])
  @flask_login.login_required
  def save_notification_preferences():
    """Saves notification preferences."""
    data = flask.request.json
    preferences = data.get("preferences")
    timezone = data.get("timezone")

    if not preferences:
      return flask.jsonify({"success": False, "error": "No data provided"}), 400

    try:
      db = utils.get_db_client()
      user_ref = db.collection("users").document(flask_login.current_user.id)
      updates = {"notification_preferences": preferences}

      if timezone:
        updates["timezone"] = timezone
        # If timezone changed, update all existing reminders
        if timezone != flask_login.current_user.timezone:
          reminders.update_user_reminders_timezone(
              flask_login.current_user.id, timezone
          )

      user_ref.update(updates)
      return flask.jsonify({"success": True})
    except Exception as e:
      app.logger.error("Failed to save preferences: %s", e)
      return flask.jsonify({"success": False, "error": str(e)}), 500


  @app.route("/settings/export_data")
  @flask_login.login_required
  def export_data_route():
    """Exports user's personal prayers as JSON."""
    try:
      prayers = utils.fetch_personal_prayers(flask_login.current_user.id)
      # Decrypt for export
      export_list = []
      for p in prayers:
        p_export = p.copy()
        if "text" in p_export:
          p_export["text"] = utils.decrypt_text(p_export["text"])
        if "for_whom" in p_export and p_export["for_whom"]:
          p_export["for_whom"] = utils.decrypt_text(p_export["for_whom"])
        export_list.append(p_export)

      response = flask.jsonify(export_list)
      response.headers["Content-Disposition"] = (
          "attachment; filename=my_prayers_export.json"
      )
      return response
    except Exception as e:
      app.logger.error("Failed to export data: %s", e)
      return "Failed to export data", 500


  @app.route("/settings/update_picture", methods=["POST"])
  @flask_login.login_required
  def update_picture():
    """Updates selected profile picture."""
    source = flask.request.form.get("pic_source")
    custom_url = flask.request.form.get("custom_pic_url")

    updates = {}

    if source == "google":
      if flask_login.current_user.google_profile_pic:
        updates["profile_pic"] = flask_login.current_user.google_profile_pic
        updates["selected_pic_source"] = "google"
    elif source == "custom":
      if custom_url:
        # The value lands in an <img src>; accept only a plausible https URL so
        # javascript:/data: schemes and junk never reach the template.
        parsed = urllib.parse.urlparse(custom_url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or len(custom_url) > 500
        ):
          flask.flash(
              "Picture URL must be an https:// image link.", "error"
          )
          return flask.redirect("/settings")
        updates["profile_pic"] = custom_url
        updates["selected_pic_source"] = "custom"

    if updates:
      try:
        db = utils.get_db_client()
        user_ref = db.collection("users").document(flask_login.current_user.id)
        user_ref.update(updates)
        flask.flash("Profile picture updated.", "success")
      except Exception as e:
        app.logger.error("Failed to update picture: %s", e)
        flask.flash("Error updating picture.", "error")

    return flask.redirect("/settings")


  @app.route("/save_dark_mode", methods=["POST"])
  @flask_login.login_required
  def save_dark_mode_route():
    """Saves dark mode preference for the current user."""
    value = flask.request.json.get("dark_mode")
    if not isinstance(value, bool):
      return flask.jsonify({"success": False, "error": "Invalid data"}), 400
    return _save_user_fields({"dark_mode": value})


  @app.route("/save_background_art", methods=["POST"])
  @flask_login.login_required
  def save_background_art_route():
    """Saves background art preference for the current user."""
    value = flask.request.json.get("background_art")
    if not isinstance(value, bool):
      return flask.jsonify({"success": False, "error": "Invalid data"}), 400
    return _save_user_fields({"background_art": value})


  @app.route("/save_hide_catechism", methods=["POST"])
  @flask_login.login_required
  def save_hide_catechism_route():
    """Saves the hide-catechism preference for the current user."""
    value = flask.request.json.get("hide_catechism")
    if not isinstance(value, bool):
      return flask.jsonify({"success": False, "error": "Invalid data"}), 400
    return _save_user_fields({"hide_catechism": value})


  @app.route("/save_font_size", methods=["POST"])
  @flask_login.login_required
  def save_font_size_route():
    """Saves font size preference for the current user."""
    value = flask.request.json.get("font_size_level")
    if not isinstance(value, int):
      return flask.jsonify({"success": False, "error": "Invalid data"}), 400
    return _save_user_fields({"font_size_level": value})


  @app.route("/toggle_favorite", methods=["POST"])
  @flask_login.login_required
  def toggle_favorite_route():
    """Toggles a favorite page for the current user."""
    data = flask.request.json
    path = data.get("path")
    title = data.get("title")

    if not path or not title:
      return (
          flask.jsonify({"success": False, "error": "Missing path or title"}),
          400,
      )

    try:
      db = utils.get_db_client()
      user_ref = db.collection("users").document(flask_login.current_user.id)

      # We need to fetch current favorites to toggle
      user_doc = user_ref.get()
      if not user_doc.exists:
        return flask.jsonify({"success": False, "error": "User not found"}), 404

      favorites = user_doc.to_dict().get("favorites", [])

      # Check if already exists (by path)
      existing_index = next(
          (i for i, f in enumerate(favorites) if f["path"] == path), -1
      )

      if existing_index >= 0:
        # Remove
        favorites.pop(existing_index)
        is_favorite = False
      else:
        # Add
        favorites.append({"path": path, "title": title})
        is_favorite = True

      user_ref.update({"favorites": favorites})
      return flask.jsonify({"success": True, "is_favorite": is_favorite})

    except Exception as e:
      app.logger.error("Failed to toggle favorite: %s", e)
      return flask.jsonify({"success": False, "error": str(e)}), 500


  @app.route("/firebase_config")
  @flask_login.login_required
  def firebase_config_route():
    """Returns Firebase configuration."""
    try:
      return flask.jsonify({
          "apiKey": secrets_fetcher.get_firebase_api_key(),
          "authDomain": "lcms-prayer-app.firebaseapp.com",
          "projectId": "lcms-prayer-app",
          "storageBucket": "lcms-prayer-app.firebasestorage.app",
          "messagingSenderId": secrets_fetcher.get_firebase_messaging_sender_id(),
          "appId": secrets_fetcher.get_firebase_app_id(),
          "vapidKey": secrets_fetcher.get_firebase_vapid_key(),
      })
    except Exception as e:
      app.logger.error("Failed to fetch Firebase config: %s", e)
      return flask.jsonify({"error": "Failed to fetch config"}), 500


  @app.route("/save_fcm_token", methods=["POST"])
  @flask_login.login_required
  def save_fcm_token_route():
    """Saves an FCM token for the user."""
    data = flask.request.json
    token = data.get("token")
    if not token:
      return flask.jsonify({"success": False, "error": "Missing token"}), 400

    try:
      db = utils.get_db_client()
      user_ref = db.collection("users").document(flask_login.current_user.id)
      user_ref.update({"fcm_tokens": firestore.ArrayUnion([token])})
      return flask.jsonify({"success": True})
    except Exception as e:
      app.logger.error("Failed to save FCM token: %s", e)
      return (
          flask.jsonify({"success": False, "error": "Database save failed"}),
          500,
      )


  @app.route("/remove_fcm_token", methods=["POST"])
  @flask_login.login_required
  def remove_fcm_token_route():
    """Removes an FCM token for the user."""
    data = flask.request.json
    token = data.get("token")
    if not token:
      return flask.jsonify({"success": False, "error": "Missing token"}), 400

    try:
      db = utils.get_db_client()
      user_ref = db.collection("users").document(flask_login.current_user.id)
      user_ref.update({"fcm_tokens": firestore.ArrayRemove([token])})
      return flask.jsonify({"success": True})
    except Exception as e:
      app.logger.error("Failed to remove FCM token: %s", e)
      return (
          flask.jsonify({"success": False, "error": "Database update failed"}),
          500,
      )
