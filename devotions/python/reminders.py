"""Functions for managing prayer reminders."""

import datetime
import uuid
import firebase_admin
from firebase_admin import messaging
from flask import current_app
import pytz
import utils

# Initialize Firebase Admin if not already initialized
if not firebase_admin._apps:
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
}

DEVOTION_URLS = {
    "morning": "/morning_devotion",
    "midday": "/midday_devotion",
    "evening": "/evening_devotion",
    "close_of_day": "/close_of_day_devotion",
    "night_watch": "/night_watch_devotion",
    "bible_in_a_year": "/bible_in_a_year",
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
    datetime.datetime.strptime(time_str, "%H:%M")
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
  current_app.logger.info(
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

  base_url = "https://www.lcmsprayer.com"
  devotion_path = DEVOTION_URLS.get(devotion_key, "/")
  full_url = f"{base_url}{devotion_path}"

  current_app.logger.info(
      f"[REMINDER] Processing reminder {reminder_id} for devotion"
      f" '{devotion_key}' via {methods}"
  )

  success_count = 0
  for method in methods:
    try:
      current_app.logger.info(
          f"[REMINDER] Sending {method} notification to user"
          f" {user_data.get('email', 'unknown')}"
      )
      send_notification(method, reminder_data, user_data, full_url)
      success_count += 1
    except Exception as e:
      current_app.logger.error(
          f"[REMINDER] Error sending {method} notification for reminder"
          f" {reminder_id}: {e}"
      )
  return success_count


def force_send_reminders_for_user(user_id):
  """Forces sending all reminders for a specific user for debugging."""
  current_app.logger.info(
      f"[REMINDER] Force sending reminders for user {user_id}"
  )
  reminders_list = get_reminders(user_id)

  if not reminders_list:
    current_app.logger.info("[REMINDER] No reminders found for user.")
    return False, "No reminders found."

  db = utils.get_db_client()
  user_doc = db.collection("users").document(user_id).get()
  if not user_doc.exists:
    current_app.logger.warning(f"[REMINDER] User {user_id} not found.")
    return False, "User not found."
  user_data = user_doc.to_dict()

  count = 0
  for r in reminders_list:
    count += _process_reminder_notification(r, user_data, r.get("id"))

  current_app.logger.info(f"[REMINDER] Force sent {count} notifications.")
  return True, f"Sent {count} notifications."


def _send_push(user_data, title, body, url):
  """Sends a push notification using Firebase Cloud Messaging."""
  tokens = user_data.get("fcm_tokens", [])
  if not tokens:
    current_app.logger.warning(f"[PUSH] No tokens found for user.")
    return

  message = messaging.MulticastMessage(
      data={
          "title": title,
          "body": body,
          "url": url,
      },
      tokens=tokens,
  )
  try:
    response = messaging.send_multicast(message)
    current_app.logger.info(f"[PUSH] Sent {response.success_count} messages.")
    if response.failure_count > 0:
      responses = response.responses
      failed_tokens = []
      for idx, resp in enumerate(responses):
        if not resp.success:
          # The order of responses corresponds to the order of the registration tokens.
          failed_tokens.append(tokens[idx])
      current_app.logger.warning(
          f"[PUSH] List of tokens that caused failures: {failed_tokens}"
      )
      # In a real app, remove invalid tokens here
  except Exception as e:
    current_app.logger.error(f"[PUSH] Error sending message: {e}")


def send_notification(method, reminder_data, user_data, devotion_url):
  """Sends a notification via the specified method."""
  devotion_name = DEVOTION_NAMES.get(reminder_data.get("devotion"))
  message = f"Time for {devotion_name}! Read here: {devotion_url}"

  if method == "push":
    _send_push(user_data, "Prayer Reminder", message, devotion_url)


def send_due_reminders():
  """Checks for reminders due at the current time and sends them."""
  current_app.logger.info("[REMINDER] Checking for due prayer reminders...")
  db = utils.get_db_client()
  now_utc = datetime.datetime.now(datetime.timezone.utc)

  # Collection Group Query
  # Requires a composite index in Firestore for 'reminders' collection group on 'next_run_utc' ASC
  query = db.collection_group(REMINDERS_COLLECTION).where(
      "next_run_utc", "<=", now_utc
  )

  docs = list(query.stream())
  current_app.logger.info(f"[REMINDER] Found {len(docs)} due reminders.")

  for doc in docs:
    data = doc.to_dict()
    user_id = data.get("user_id")

    # Fetch user data for contact info
    user_doc = db.collection("users").document(user_id).get()
    if not user_doc.exists:
      current_app.logger.warning(
          f"[REMINDER] User {user_id} not found, skipping reminder {doc.id}"
      )
      continue
    user_data = user_doc.to_dict()

    _process_reminder_notification(data, user_data, doc.id)

    # Schedule next run
    try:
      # Calculate next run from the *scheduled* time to avoid drift,
      # or from now if we want to reset base.
      # Better to recalculate from "now" to ensure it's in the future.
      next_run = calculate_next_run(data.get("time"), data.get("timezone"))
      current_app.logger.info(
          f"[REMINDER] Rescheduling reminder {doc.id} to {next_run}"
      )
      doc.reference.update({"next_run_utc": next_run})
    except Exception as e:
      current_app.logger.error(
          f"[REMINDER] Error rescheduling reminder {doc.id}: {e}"
      )

  return True
