"""JSON API, reminder, streak, cron-task, and webhook routes."""

import datetime
import secrets

import flask
import flask_login
import models
from routes.settings import _save_user_fields
import secrets_fetcher
from services import fullofeyes_scraper
from services import prayer_requests
from services import reminders
from services import users
import streak_logic
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
import utils


def register(app, *, admin_required, rate_limited):
  """Registers the API/task/webhook routes on the app."""

  @app.route("/api/save_reading_preference", methods=["POST"])
  @flask_login.login_required
  def save_reading_preference_route():
    """Saves reading preference for a specific devotion."""
    data = flask.request.json
    devotion = data.get("devotion")
    preference = data.get("preference")

    if not devotion or not preference:
      return flask.jsonify({"success": False, "error": "Missing fields"}), 400

    return _save_user_fields(
        {f"reading_preferences.{devotion}": preference}, use_merge=False
    )


  @app.route("/api/save_psalm_preference", methods=["POST"])
  @flask_login.login_required
  def save_psalm_preference_route():
    """Saves psalm preference for a specific devotion."""
    data = flask.request.json
    devotion = data.get("devotion")
    preference = data.get("preference")

    if not devotion or not preference:
      return flask.jsonify({"success": False, "error": "Missing fields"}), 400

    return _save_user_fields(
        {f"psalm_preferences.{devotion}": preference}, use_merge=False
    )


  @app.route("/api/random_prayer_request")
  # Unauthenticated Firestore read on every call.
  @rate_limited("random_prayer_request", 30, 60)
  def random_prayer_request_route():
    """Returns a random active prayer request."""
    exclude_user_id = None
    if flask_login.current_user.is_authenticated:
      exclude_user_id = flask_login.current_user.id

    prayer = prayer_requests.get_random_prayer_request(
        exclude_user_id=exclude_user_id
    )
    if prayer:
      return flask.jsonify({"success": True, "prayer": prayer})
    else:
      return flask.jsonify({
          "success": False,
          "message": "No active prayer requests found.",
      })


  @app.route("/api/lectionary/art")
  def lectionary_art_route():
    """Fetches relevant art based on a query."""
    ref = flask.request.args.get("ref")
    theme = flask.request.args.get("theme")
    art = fullofeyes_scraper.get_art_for_reading(ref, fallback_theme=theme)
    return flask.jsonify(art) if art else flask.jsonify({})


  @app.route("/api/art/recent")
  def art_recent_route():
    """Fetches a random recent image."""
    ttl_key = int(datetime.datetime.now().timestamp() // 3600)
    images = fullofeyes_scraper.fetch_recent_images_cached(ttl_key)
    if images:
      return flask.jsonify(secrets.choice(images))
    return flask.jsonify({})


  @app.route("/api/complete_prayer", methods=["POST"])
  @flask_login.login_required
  def complete_prayer_route():
    """Marks a prayer as complete and updates the streak."""
    data = flask.request.json
    devotion_type = data.get("devotion_type", "unknown")
    bible_year_day = data.get("bible_year_day")

    user_id = flask_login.current_user.id
    timezone_str = flask_login.current_user.timezone or "America/New_York"

    result = users.process_prayer_completion(
        user_id, devotion_type, timezone_str, bible_year_day
    )

    if result:
      return flask.jsonify(result)
    else:
      return flask.jsonify({"error": "User not found"}), 404


  @app.route("/api/complete_bible_reading", methods=["POST"])
  @flask_login.login_required
  def complete_bible_reading_route():
    """Marks a Bible reading as complete."""
    data = flask.request.json
    day = data.get("day")
    if not day:
      return flask.jsonify({"error": "Missing day"}), 400

    user_id = flask_login.current_user.id
    timezone_str = flask_login.current_user.timezone or "America/New_York"

    result = users.process_bible_reading_completion(user_id, day, timezone_str)
    if result:
      return flask.jsonify(result)
    else:
      return flask.jsonify({"error": "Failed to update"}), 500


  @app.route("/api/catch_up_bible_readings", methods=["POST"])
  @flask_login.login_required
  def catch_up_bible_readings_route():
    """Marks multiple Bible readings as complete."""
    data = flask.request.json
    days = data.get("days")
    if not days or not isinstance(days, list):
      return flask.jsonify({"error": "Invalid days list"}), 400

    user_id = flask_login.current_user.id
    result = users.mark_bible_days_completed(user_id, days)

    if result:
      return flask.jsonify(result)
    else:
      return flask.jsonify({"error": "Failed to update"}), 500


  @app.route("/api/toggle_memorized_verse", methods=["POST"])
  @flask_login.login_required
  def toggle_memorized_verse_route():
    """Toggles the memorized status of a verse."""
    data = flask.request.json
    verse_id = data.get("verse_id")
    if not verse_id:
      return flask.jsonify({"error": "Missing verse_id"}), 400

    result = users.toggle_memorized_verse(flask_login.current_user.id, verse_id)
    if result:
      return flask.jsonify(result)
    return flask.jsonify({"error": "Failed"}), 500


  @app.route("/api/mark_catechism_complete", methods=["POST"])
  @flask_login.login_required
  def mark_catechism_complete_route():
    """Marks a catechism section as complete."""
    data = flask.request.json
    section_index = data.get("section_index")
    if section_index is None:
      return flask.jsonify({"error": "Missing section_index"}), 400

    result = users.mark_catechism_complete(
        flask_login.current_user.id, section_index
    )
    if result:
      return flask.jsonify(result)
    return flask.jsonify({"error": "Failed"}), 500


  @app.route("/complete_prayer_email/<token>")
  # Unauthenticated token redemption -- the cap makes guessing tokens by
  # volume impractical while leaving real email-link clicks unaffected.
  @rate_limited("complete_prayer_email", 15, 600)
  def complete_prayer_email_route(token):
    """Marks prayer as complete from an email link."""
    data = users.verify_completion_token(token)
    if not data:
      return (
          (
              "Invalid or expired token. You may have already completed this"
              " prayer or waited too long."
          ),
          400,
      )

    user_id = data.get("uid")
    devotion_type = data.get("dt")
    bible_year_day = data.get("byd")

    # We use the user's stored timezone or default
    user = models.User.get(user_id)
    if not user:
      return "User not found.", 404

    timezone_str = user.timezone or "America/New_York"
    result = users.process_prayer_completion(
        user_id, devotion_type, timezone_str, bible_year_day
    )

    if result:
      return flask.render_template(
          "prayer_completed.html",
          message=result.get("message", "Prayer recorded!"),
          streak=result.get("streak", 0),
      )
    else:
      return "Failed to record prayer.", 500


  @app.route("/save_bia_progress", methods=["POST"])
  @flask_login.login_required
  def save_bia_progress_route():
    """Saves Bible in a Year progress for the current user."""
    data = flask.request.json
    day = data.get("day")
    last_visit = data.get("last_visit")
    if isinstance(day, int) and last_visit:
      try:
        utils.save_bia_progress(flask_login.current_user.id, day, last_visit)
        return flask.jsonify({"success": True})
      except Exception as e:
        app.logger.error("Failed to save BIA progress: %s", e)
        return (
            flask.jsonify({"success": False, "error": "Database save failed"}),
            500,
        )
    return (
        flask.jsonify({"success": False, "error": "Invalid progress data"}),
        400,
    )


  @app.route("/reminders")
  @flask_login.login_required
  def reminders_route():
    """Returns the reminders page."""
    return flask.render_template("reminders.html")


  @app.route("/add_reminder", methods=["POST"])
  @flask_login.login_required
  def add_reminder_route():
    """Adds a prayer reminder."""
    data = flask.request.json
    # We no longer strictly need phone_number passed here if it's in the profile,
    # but we can accept it if the frontend sends it to update/verify.
    # For now, let's assume the frontend calls /save_contact_info separately
    # or we pass it through.

    success, error = reminders.add_reminder(
        flask_login.current_user.id,
        data.get("time"),
        data.get("devotion"),
        data.get("timezone"),
        data.get("reading_type"),
        data.get("psalm_type"),
    )
    if success:
      return flask.jsonify({"success": True})
    return flask.jsonify({"success": False, "error": error}), 400


  @app.route("/get_reminders")
  @flask_login.login_required
  def get_reminders_route():
    """Gets user reminders."""
    user_reminders = reminders.get_reminders(flask_login.current_user.id)
    return flask.jsonify(user_reminders)


  @app.route("/delete_reminder", methods=["POST"])
  @flask_login.login_required
  def delete_reminder_route():
    """Deletes a reminder."""
    data = flask.request.json
    reminder_id = data.get("reminder_id")
    if reminders.delete_reminder(flask_login.current_user.id, reminder_id):
      return flask.jsonify({"success": True})
    return flask.jsonify({"success": False, "error": "Failed to delete"}), 500


  def _is_authorized_task_request():
    """Returns True if the caller is an authorized cron/task invoker.

    Accepts the App Engine / Cloud Scheduler cron header (which Google strips from
    external requests) or a shared secret in X-Tasks-Secret matching TASKS_SECRET.
    When TASKS_SECRET is unset the endpoint stays open (its prior behavior) but
    logs a warning, so deploying this change doesn't break an existing scheduler
    before the secret and the scheduler's header are wired up.
    """
    if flask.request.headers.get("X-Appengine-Cron") == "true":
      return True
    expected = secrets_fetcher.get_tasks_secret()
    if not expected:
      app.logger.warning(
          "/tasks/send_reminders invoked without TASKS_SECRET configured;"
          " allowing unauthenticated. Set TASKS_SECRET to enforce."
      )
      return True
    provided = flask.request.headers.get("X-Tasks-Secret", "")
    if secrets.compare_digest(provided, expected):
      return True
    app.logger.warning(
        "Rejected /tasks/send_reminders: missing or invalid X-Tasks-Secret."
    )
    return False


  @app.route("/tasks/send_reminders")
  def send_reminders_task():
    """Cron task to send due reminders."""
    if not _is_authorized_task_request():
      return flask.abort(403)
    reminders.send_due_reminders()
    return "OK", 200


  @app.route("/debug/force_reminders", methods=["POST"])
  @flask_login.login_required
  @admin_required
  def force_reminders_route():
    success, msg = reminders.force_send_reminders_for_user(
        flask_login.current_user.id
    )
    if success:
      return flask.jsonify({"success": True, "message": msg})
    else:
      return flask.jsonify({"success": False, "error": msg}), 400


  @app.route("/streaks")
  @flask_login.login_required
  def streaks_route():
    """Renders the streaks and achievements page."""
    user = flask_login.current_user

    # Prayer Streak Logic
    current_streak = user.streak_count
    next_milestone = 7
    milestones = [7, 30, 90, 180, 270, 365]

    for m in milestones:
      if current_streak < m:
        next_milestone = m
        break
    if current_streak >= 365:
      next_milestone = current_streak + (90 - ((current_streak - 365) % 90))

    progress_percent = min(100, (current_streak / next_milestone) * 100)

    # Bible Streak Logic
    bible_streak = getattr(user, "bible_streak_count", 0)
    bible_next_milestone = 7
    for m in milestones:
      if bible_streak < m:
        bible_next_milestone = m
        break
    if bible_streak >= 365:
      bible_next_milestone = bible_streak + (90 - ((bible_streak - 365) % 90))

    bible_progress_percent = min(100, (bible_streak / bible_next_milestone) * 100)

    # Gamification Stats
    prayed_for_others_count = len(user.prayed_request_ids)
    memorized_verses_count = len(user.memorized_verses)

    catechism_total = len(utils.get_catechism_sections())
    catechism_completed = len(user.completed_catechism_sections)
    catechism_pct = 0
    if catechism_total > 0:
      catechism_pct = int((catechism_completed / catechism_total) * 100)

    # Today (in the user's timezone) drives the "prayed/read today" flags and the
    # time-of-day devotion recommendation below.
    now = utils.now_for_user(user)
    today_str = now.strftime("%Y-%m-%d")
    prayed_today = user.last_prayer_date == today_str

    # Whether a grace day is currently available to protect the prayer streak.
    prayer_grace_available = streak_logic.grace_available(
        streak_logic.parse_ymd(user.last_prayer_grace_date), now.date()
    )

    # Determine if read bible today
    read_bible_today = user.last_bible_reading_date == today_str

    # Count devotions today
    devotions_today_count = 0
    if user.completed_devotions:
      for ts_str in user.completed_devotions.values():
        if ts_str.startswith(today_str):
          devotions_today_count += 1

    # Determine recommended devotion
    hour = now.hour
    if 5 <= hour < 11:
      recommended_devotion = {
          "name": "Morning Prayer",
          "url": "/morning_devotion",
      }
    elif 11 <= hour < 15:
      recommended_devotion = {"name": "Midday Prayer", "url": "/midday_devotion"}
    elif 15 <= hour < 20:
      recommended_devotion = {
          "name": "Evening Prayer",
          "url": "/evening_devotion",
      }
    elif 0 <= hour < 5:
      recommended_devotion = {
          "name": "Night Watch",
          "url": "/night_watch_devotion",
      }
    else:
      recommended_devotion = {
          "name": "Close of the Day",
          "url": "/close_of_day_devotion",
      }

    return flask.render_template(
        "streaks.html",
        current_streak=current_streak,
        next_milestone=next_milestone,
        progress_percent=progress_percent,
        prayed_today=prayed_today,
        prayer_grace_available=prayer_grace_available,
        devotions_today_count=devotions_today_count,
        achievements=user.achievements,
        recommended_devotion=recommended_devotion,
        bible_streak=bible_streak,
        read_bible_today=read_bible_today,
        bible_next_milestone=bible_next_milestone,
        bible_progress_percent=bible_progress_percent,
        prayed_for_others_count=prayed_for_others_count,
        memorized_verses_count=memorized_verses_count,
        catechism_completed=catechism_completed,
        catechism_total=catechism_total,
        catechism_pct=catechism_pct,
    )


  @app.route("/twilio/sms_reply", methods=["POST"])
  def twilio_sms_reply():
    """Handles incoming SMS replies from Twilio."""
    # Reject forged webhooks. Twilio signs every request with the account auth
    # token over the full URL + POST params, so verifying X-Twilio-Signature stops
    # a spoofed STOP from disabling someone's SMS. If the token isn't configured
    # (e.g. a non-prod environment) validation is skipped with a warning.
    auth_token = secrets_fetcher.get_twilio_api_key()
    if auth_token:
      validator = RequestValidator(auth_token)
      signature = flask.request.headers.get("X-Twilio-Signature", "")
      if not validator.validate(
          flask.request.url, flask.request.form, signature
      ):
        app.logger.warning(
            "Rejected Twilio webhook with invalid signature (url=%s)",
            flask.request.url,
        )
        return flask.abort(403)
    else:
      app.logger.warning(
          "Twilio auth token not configured; skipping webhook signature check."
      )

    incoming_msg = flask.request.values.get("Body", "").strip().upper()
    from_number = flask.request.values.get("From", "")

    resp = MessagingResponse()

    if incoming_msg == "STOP":
      # Logic to find user and disable SMS for the last sent type
      try:
        db = utils.get_db_client()
        users_ref = db.collection("users")
        # Query by phone number
        query = users_ref.where("phone_number", "==", from_number).limit(1)
        results = list(query.stream())

        if results:
          user_doc = results[0]
          user_data = user_doc.to_dict()
          last_type = user_data.get("last_sms_type")

          if last_type:
            # Update preference
            current_prefs = user_data.get("notification_preferences", {})
            if last_type in current_prefs:
              current_prefs[last_type]["sms"] = False
              user_doc.reference.update(
                  {"notification_preferences": current_prefs}
              )

              readable_type = last_type.replace("_", " ").title()
              resp.message(
                  f"You have been unsubscribed from {readable_type} SMS"
                  " notifications."
              )
            else:
              resp.message("You have been unsubscribed from SMS notifications.")
          else:
            # Fallback: Disable all SMS? Or just generic message.
            # Let's assume generic stop for now if we can't find the type.
            # Or maybe we shouldn't modify anything if we don't know what to stop,
            # but Twilio might block us anyway.
            # Best effort: disable 'prayer_reminders' as default
            current_prefs = user_data.get("notification_preferences", {})
            updated = False
            if "prayer_reminders" in current_prefs:
              current_prefs["prayer_reminders"]["sms"] = False
              updated = True

            if updated:
              user_doc.reference.update(
                  {"notification_preferences": current_prefs}
              )
              resp.message("You have been unsubscribed from SMS reminders.")
            else:
              resp.message("You have been unsubscribed.")

        else:
          app.logger.warning(
              f"Twilio STOP received from unknown number: {from_number}"
          )
          resp.message("You have been unsubscribed.")

      except Exception as e:
        app.logger.error(f"Error handling Twilio reply: {e}")
        resp.message("Error processing request.")

    return str(resp)
