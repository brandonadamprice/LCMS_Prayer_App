"""Functions for managing prayer reminders."""

import datetime
import uuid
import firebase_admin
from firebase_admin import messaging
import flask
import pytz
import secrets_fetcher
from twilio.rest import Client
import utils

# Initialize Firebase Admin if not already initialized
try:
  firebase_admin.get_app()
except ValueError:
  # Explicitly set project ID to ensure correct FCM endpoint usage
  firebase_admin.initialize_app(options={"projectId": "lcms-prayer-app"})

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


def add_reminder(user_id, time_str, devotion, methods, timezone):
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


def _process_reminder_notification(reminder_data, user_data, reminder_id=None):
  """Helper to process and send a single reminder notification."""
  methods = reminder_data.get("methods", [])
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

  base_url = "https://www.asimplewaytopray.com"
  devotion_path = DEVOTION_URLS.get(devotion_key, "/")
  full_url = f"{base_url}{devotion_path}"

  flask.current_app.logger.info(
      f"[REMINDER] Processing reminder {reminder_id} for devotion"
      f" '{devotion_key}' via {methods}"
  )

  success_count = 0
  for method in methods:
    try:
      flask.current_app.logger.info(
          f"[REMINDER] Sending {method} notification to user"
          f" {user_data.get('email', 'unknown')}"
      )
      send_notification(method, reminder_data, user_data, full_url)
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
    flask.current_app.logger.warning(f"[PUSH] No tokens found for user.")
    return

  success_count = 0
  failure_count = 0
  failed_tokens = []

  # We send individually to avoid 404 errors with the /batch endpoint
  # that send_multicast uses, which can occur in some environments.
  for token in tokens:
    try:
      message = messaging.Message(
          data={
              "title": title,
              "body": body,
              "url": url,
          },
          token=token,
      )
      messaging.send(message)
      success_count += 1
    except Exception as e:
      failure_count += 1
      failed_tokens.append(token)
      flask.current_app.logger.warning(
          f"[PUSH] Failed to send to token {token}: {e}"
      )

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


def _send_sms(user_data, message, notification_type=None):
  """Sends an SMS notification via Twilio and updates last_sms_type."""
  phone = user_data.get("phone_number")
  if not phone:
    flask.current_app.logger.warning(
        f"[SMS] No phone number for user {user_data.get('email')}"
    )
    return

  try:
    sid = secrets_fetcher.get_twilio_account_sid()
    token = secrets_fetcher.get_twilio_api_key()
    from_number = secrets_fetcher.get_twilio_phone_number()

    if not (sid and token and from_number):
      flask.current_app.logger.warning(
          "[SMS] Missing Twilio credentials (SID, API Key, or Phone Number)."
      )
      return

    # Append opt-out instruction
    full_message = f"{message}\n\nRespond STOP to stop these text messages."

    client = Client(sid, token)
    msg = client.messages.create(body=full_message, from_=from_number, to=phone)
    flask.current_app.logger.info(f"[SMS] Sent SMS to {phone}: {msg.sid}")

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
