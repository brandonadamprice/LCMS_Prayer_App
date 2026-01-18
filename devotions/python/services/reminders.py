"""Functions for managing prayer reminders."""

import datetime
import uuid

import communication
from devotional_content import bible_in_a_year
from devotional_content import close_of_day
from devotional_content import evening
from devotional_content import lent
from devotional_content import midday
from devotional_content import morning
from devotional_content import night_watch
import flask
import pytz
from services import users
import utils

REMINDERS_COLLECTION = "reminders"

DEVOTION_NAMES = {
    "morning": "Morning Prayer",
    "midday": "Midday Prayer",
    "evening": "Evening Prayer",
    "close_of_day": "Close of the Day",
    "night_watch": "Night Watch",
    "bible_in_a_year": "Bible in a Year",
    "lent": "Lenten Devotion",
}

DEVOTION_URLS = {
    "morning": "/morning_devotion",
    "midday": "/midday_devotion",
    "evening": "/evening_devotion",
    "close_of_day": "/close_of_day_devotion",
    "night_watch": "/night_watch_devotion",
    "bible_in_a_year": "/bible_in_a_year",
    "lent": "/lent_devotion",
}


def calculate_next_run(time_str, timezone_str):
  """Calculates the next occurrence of time_str in UTC."""
  try:
    tz = pytz.timezone(timezone_str)
  except pytz.UnknownTimeZoneError:
    tz = pytz.UTC

  now = datetime.datetime.now(tz)
  hour, minute = map(int, time_str.split(":"))

  # Create candidate time for today
  candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

  # If candidate is in the past, schedule for tomorrow
  if candidate <= now:
    candidate += datetime.timedelta(days=1)

  return candidate.astimezone(pytz.UTC)


def add_reminder(
    user_id, time_str, devotion, methods, timezone, reading_type=None
):
  """Adds a new reminder for a user."""
  if not user_id or not time_str or not devotion or not methods:
    return False, "Missing required fields."

  # Basic validation of time format HH:MM
  try:
    dt = datetime.datetime.strptime(time_str, "%H:%M")
    if dt.minute % 15 != 0:
      return (
          False,
          "Time must be in 15-minute increments (e.g. :00, :15, :30, :45).",
      )
  except ValueError:
    return False, "Invalid time format."

  db = utils.get_db_client()
  reminder_id = str(uuid.uuid4())

  # Calculate next run time
  next_run_utc = calculate_next_run(time_str, timezone)

  reminder_data = {
      "user_id": user_id,
      "time": time_str,
      "devotion": devotion,
      "methods": methods,
      "timezone": timezone,
      "reading_type": reading_type,
      "created_at": datetime.datetime.now(datetime.timezone.utc),
      "next_run_utc": next_run_utc,
  }

  # Using a subcollection. To query across all users, we'll use a Collection Group query.
  # This requires an index on 'next_run_utc' for the 'reminders' collection group.
  user_ref = db.collection("users").document(user_id)
  user_ref.collection(REMINDERS_COLLECTION).document(reminder_id).set(
      reminder_data
  )

  return True, None


def get_reminders(user_id):
  """Fetches all reminders for a user."""
  db = utils.get_db_client()
  docs = (
      db.collection("users")
      .document(user_id)
      .collection(REMINDERS_COLLECTION)
      .stream()
  )
  reminders = []
  for doc in docs:
    data = doc.to_dict()
    data["id"] = doc.id
    data["devotion_name"] = DEVOTION_NAMES.get(
        data.get("devotion"), data.get("devotion")
    )
    reminders.append(data)
  return reminders


def delete_reminder(user_id, reminder_id):
  """Deletes a reminder."""
  flask.current_app.logger.info(
      f"[REMINDER] Deleting reminder {reminder_id} for user {user_id}"
  )
  db = utils.get_db_client()
  ref = (
      db.collection("users")
      .document(user_id)
      .collection(REMINDERS_COLLECTION)
      .document(reminder_id)
  )
  # Verify ownership implicitly by path
  ref.delete()
  return True


def update_user_reminders_timezone(user_id, new_timezone):
  """Updates timezone for all reminders of a user and recalculates next_run_utc."""
  flask.current_app.logger.info(
      f"[REMINDER] Updating timezone to {new_timezone} for user {user_id}"
  )
  reminders = get_reminders(user_id)
  db = utils.get_db_client()

  for r in reminders:
    try:
      next_run = calculate_next_run(r["time"], new_timezone)
      ref = (
          db.collection("users")
          .document(user_id)
          .collection(REMINDERS_COLLECTION)
          .document(r["id"])
      )
      ref.update({"timezone": new_timezone, "next_run_utc": next_run})
    except Exception as e:
      flask.current_app.logger.error(
          f"[REMINDER] Failed to update reminder {r.get('id')}: {e}"
      )
  return True


def _process_reminder_notification(reminder_data, user_data, reminder_id=None):
  """Helper to process and send a single reminder notification."""
  # Always check all methods; actual sending depends on user preferences.
  methods = ["push", "email", "sms"]
  devotion_key = reminder_data.get("devotion")

  # Lenten Season Check
  if devotion_key == "lent":
    eastern_timezone = pytz.timezone("America/New_York")
    now = datetime.datetime.now(eastern_timezone)
    cy = utils.ChurchYear(now.year)
    # Check if within Lent (Ash Wednesday to Easter Sunday inclusive)
    if not (cy.ash_wednesday <= now.date() <= cy.easter_date):
      flask.current_app.logger.info(
          f"[REMINDER] Skipping Lenten reminder {reminder_id} as it is not"
          " Lent."
      )
      return 0

  # Prepare URLs
  base_url = "https://www.asimplewaytopray.com"
  relative_path = DEVOTION_URLS.get(devotion_key, "/")

  reading_type = reminder_data.get("reading_type")
  if reading_type == "lectionary":
    relative_path += "?reading_type=lectionary"

  flask.current_app.logger.info(
      f"[REMINDER] Processing reminder {reminder_id} for devotion"
      f" '{devotion_key}' via {methods}"
  )

  success_count = 0
  for method in methods:
    # Use relative URL for push (PWA scope), absolute for email/SMS
    if method == "push":
      url_to_use = relative_path
    else:
      url_to_use = f"{base_url}{relative_path}"

    try:
      flask.current_app.logger.info(
          f"[REMINDER] Sending {method} notification to user"
          f" {user_data.get('email', 'unknown')}"
      )
      send_notification(method, reminder_data, user_data, url_to_use)
      success_count += 1
    except Exception as e:
      flask.current_app.logger.error(
          f"[REMINDER] Error sending {method} notification for reminder"
          f" {reminder_id}: {e}"
      )
  return success_count


def force_send_reminders_for_user(user_id):
  """Forces sending all reminders for a specific user for debugging."""
  flask.current_app.logger.info(
      f"[REMINDER] Force sending reminders for user {user_id}"
  )
  reminders_list = get_reminders(user_id)

  if not reminders_list:
    flask.current_app.logger.info("[REMINDER] No reminders found for user.")
    return False, "No reminders found."

  db = utils.get_db_client()
  user_doc = db.collection("users").document(user_id).get()
  if not user_doc.exists:
    flask.current_app.logger.warning(f"[REMINDER] User {user_id} not found.")
    return False, "User not found."
  user_data = user_doc.to_dict()
  user_data["id"] = user_id  # Ensure ID is available

  count = 0
  for r in reminders_list:
    count += _process_reminder_notification(r, user_data, r.get("id"))

  flask.current_app.logger.info(f"[REMINDER] Force sent {count} notifications.")
  return True, f"Sent {count} notifications."


def _send_push(user_data, title, body, url):
  """Sends a push notification using Firebase Cloud Messaging."""
  tokens = user_data.get("fcm_tokens", [])
  if not tokens:
    flask.current_app.logger.warning("[PUSH] No tokens found for user.")
    return

  success_count = 0
  failure_count = 0
  failed_tokens = []

  # We send individually to avoid 404 errors with the /batch endpoint
  # that send_multicast uses, which can occur in some environments.
  for token in tokens:
    if communication.send_push(token, title, body, url):
      success_count += 1
    else:
      failure_count += 1
      failed_tokens.append(token)

  flask.current_app.logger.info(
      f"[PUSH] Sent {success_count} messages. Failed: {failure_count}"
  )
  if failed_tokens:
    flask.current_app.logger.warning(f"[PUSH] Failed tokens: {failed_tokens}")


def send_generic_push_to_user(user_id, title, body, url):
  """Sends a generic push notification to a user by ID."""
  db = utils.get_db_client()
  user_doc = db.collection("users").document(user_id).get()
  if not user_doc.exists:
    flask.current_app.logger.warning(f"[PUSH] User {user_id} not found.")
    return
  user_data = user_doc.to_dict()
  _send_push(user_data, title, body, url)


def send_generic_notification_to_user(
    user_id, title, body, url, notification_type
):
  """Sends a generic notification to a user by ID, checking preferences."""
  db = utils.get_db_client()
  user_doc = db.collection("users").document(user_id).get()
  if not user_doc.exists:
    flask.current_app.logger.warning(f"[NOTIF] User {user_id} not found.")
    return
  user_data = user_doc.to_dict()
  user_data["id"] = user_id

  preferences = user_data.get("notification_preferences", {})
  # Default to True/False for push/sms if not set
  type_prefs = preferences.get(notification_type, {"push": True, "sms": False})

  if type_prefs.get("push"):
    _send_push(user_data, title, body, url)

  if type_prefs.get("sms"):
    _send_sms(user_data, body, notification_type)


def send_notification(method, reminder_data, user_data, devotion_url):
  """Sends a notification via the specified method."""
  devotion_name = DEVOTION_NAMES.get(reminder_data.get("devotion"))
  message = f"Time for {devotion_name}! Read here: {devotion_url}"

  # Check user preferences
  preferences = user_data.get("notification_preferences", {})
  reminder_prefs = preferences.get(
      "prayer_reminders", {"push": True, "sms": False}
  )

  if method == "push":
    if reminder_prefs.get("push"):
      _send_push(user_data, "Prayer Reminder", message, devotion_url)
    else:
      flask.current_app.logger.info(
          "[REMINDER] Push disabled by user preference for user"
          f" {user_data.get('email')}"
      )

  elif method == "sms":
    if reminder_prefs.get("sms"):
      _send_sms(user_data, message, "prayer_reminders")
    else:
      flask.current_app.logger.info(
          "[REMINDER] SMS disabled by user preference for user"
          f" {user_data.get('email')}"
      )

  elif method == "email":
    if reminder_prefs.get("email"):
      _send_email(
          user_data,
          devotion_url,
          reminder_data.get("devotion"),
          reminder_data.get("reading_type"),
      )
    else:
      flask.current_app.logger.info(
          "[REMINDER] Email disabled by user preference for user"
          f" {user_data.get('email')}"
      )


def _send_email(user_data, devotion_url, devotion_key, reading_type):
  """Sends an email with the devotion content."""
  email = user_data.get("email")
  if not email:
    return

  try:
    data = None
    title = DEVOTION_NAMES.get(devotion_key, "Daily Prayer")
    template_name = None

    if devotion_key == "morning":
      data = morning.get_morning_devotion_data(user_data.get("id"))
      template_name = "morning_devotion.html"
    elif devotion_key == "midday":
      data = midday.get_midday_devotion_data(user_data.get("id"))
      template_name = "midday_devotion.html"
    elif devotion_key == "evening":
      data = evening.get_evening_devotion_data(user_data.get("id"))
      template_name = "evening_devotion.html"
    elif devotion_key == "close_of_day":
      data = close_of_day.get_close_of_day_devotion_data(user_data.get("id"))
      template_name = "close_of_day_devotion.html"
    elif devotion_key == "night_watch":
      data = night_watch.get_night_watch_devotion_data(user_data.get("id"))
      template_name = "night_watch_devotion.html"
    elif devotion_key == "bible_in_a_year":
      data = bible_in_a_year.get_bible_in_a_year_devotion_data(
          user_data.get("id")
      )
      template_name = "bible_in_a_year.html"
    elif devotion_key == "lent":
      data = lent.get_lent_devotion_data()
      template_name = "lent_devotion.html"

    if data and template_name:
      if reading_type == "lectionary" and devotion_key in [
          "morning",
          "midday",
          "evening",
          "close_of_day",
          "night_watch",
      ]:
        # Swap reading references and texts to lectionary versions if available
        if data.get("daily_lectionary_readings"):
          data["office_reading_style"] = "display: none;"
          data["lectionary_reading_style"] = "display: block;"
        else:
          data["office_reading_style"] = "display: block;"
          data["lectionary_reading_style"] = "display: none;"
      else:
        data["office_reading_style"] = "display: block;"
        data["lectionary_reading_style"] = "display: none;"

      # Also need user info for potential personalization
      data["current_user"] = (
          user_data  # Though templates use flask_login.current_user usually
      )
      data["devotion_url"] = devotion_url

      # Generate Completion Link
      if "id" in user_data:
        # We need the current date for the streak calculation in process_prayer_completion
        # Ideally, we use the date for which the devotion was generated (today)
        eastern_timezone = pytz.timezone("America/New_York")
        now = datetime.datetime.now(eastern_timezone)
        today_str = now.strftime("%Y-%m-%d")

        # Determine Bible Year Day if applicable
        bible_year_day = None
        if reading_type == "bible_in_a_year":
          # If the user selected 'bible_in_a_year' reading for a standard devotion
          # We need to find what day they are on.
          # The data dictionary should contain 'bible_in_a_year_data' if we added it to get_morning_devotion_data etc.
          # But we haven't done that yet.
          # However, get_bible_in_a_year_devotion_data ALREADY returns 'day_number'
          if devotion_key == "bible_in_a_year":
            bible_year_day = data.get("day_number")
          # For other devotions, we need to fetch it if reading_type is set.
          # We will implement logic in the devotion generators to include this data.
          elif data.get("bible_in_a_year_reading"):
            bible_year_day = data["bible_in_a_year_reading"].get("day_number")

        token = users.get_completion_token(
            user_data["id"], devotion_key, today_str, bible_year_day
        )
        base_url = "https://www.asimplewaytopray.com"
        completion_link = f"{base_url}/complete_prayer_email/{token}"
        data["completion_link"] = completion_link

      body = flask.render_template(
          template_name, parent_template="email_base.html", **data
      )
    else:
      flask.current_app.logger.error(
          f"[EMAIL] No data or template for {devotion_key}"
      )
      return

    subject = f"{title} - {datetime.date.today().strftime('%A, %b %d')}"
    communication.send_email(email, subject, body_html=body)

  except Exception as e:
    flask.current_app.logger.error(f"[EMAIL] Failed to send email: {e}")


def _send_sms(user_data, message, notification_type=None):
  """Sends an SMS notification via Twilio and updates last_sms_type."""
  phone = user_data.get("phone_number")
  if not phone:
    flask.current_app.logger.warning(
        f"[SMS] No phone number for user {user_data.get('email')}"
    )
    return

  try:
    # Append opt-out instruction
    full_message = f"{message}\n\nRespond STOP to stop these text messages."

    if communication.send_sms(phone, full_message):
      # Update user's last_sms_type for STOP handling
      if notification_type and "id" in user_data:
        db = utils.get_db_client()
        db.collection("users").document(user_data["id"]).update(
            {"last_sms_type": notification_type}
        )

  except Exception as e:
    flask.current_app.logger.error(f"[SMS] Failed to send SMS: {e}")


def send_due_reminders():
  """Checks for reminders due at the current time and sends them."""
  flask.current_app.logger.info(
      "[REMINDER] Checking for due prayer reminders..."
  )

  db = utils.get_db_client()
  now_utc = datetime.datetime.now(datetime.timezone.utc)

  # Collection Group Query
  # Requires a composite index in Firestore for 'reminders' collection group on 'next_run_utc' ASC
  query = db.collection_group(REMINDERS_COLLECTION).where(
      "next_run_utc", "<=", now_utc
  )

  docs = list(query.stream())
  flask.current_app.logger.info(f"[REMINDER] Found {len(docs)} due reminders.")

  for doc in docs:
    data = doc.to_dict()
    user_id = data.get("user_id")

    # Fetch user data for contact info
    user_doc = db.collection("users").document(user_id).get()
    if not user_doc.exists:
      flask.current_app.logger.warning(
          f"[REMINDER] User {user_id} not found, skipping reminder {doc.id}"
      )
      continue
    user_data = user_doc.to_dict()
    user_data["id"] = user_id

    _process_reminder_notification(data, user_data, doc.id)

    # Schedule next run
    try:
      # Calculate next run from the *scheduled* time to avoid drift,
      # or from now if we want to reset base.
      # Better to recalculate from "now" to ensure it's in the future.
      next_run = calculate_next_run(data.get("time"), data.get("timezone"))
      flask.current_app.logger.info(
          f"[REMINDER] Rescheduling reminder {doc.id} to {next_run}"
      )
      doc.reference.update({"next_run_utc": next_run})
    except Exception as e:
      flask.current_app.logger.error(
          f"[REMINDER] Error rescheduling reminder {doc.id}: {e}"
      )

  return True
