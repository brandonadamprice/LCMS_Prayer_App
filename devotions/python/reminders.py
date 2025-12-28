"""Functions for managing prayer reminders."""

import datetime

import uuid
import firebase_admin
from firebase_admin import messaging
import pytz
import utils

# Initialize Firebase Admin if not already initialized
if not firebase_admin._apps:
    firebase_admin.initialize_app()

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


def _send_push(user_data, title, body, url):
  """Sends a push notification using Firebase Cloud Messaging."""
  tokens = user_data.get("fcm_tokens", [])
  if not tokens:
    print(f"[PUSH] No tokens found for user.")
    return

  message = messaging.MulticastMessage(
      notification=messaging.Notification(
          title=title,
          body=body,
      ),
      data={"url": url},
      tokens=tokens,
  )
  try:
    response = messaging.send_multicast(message)
    print(f"[PUSH] Sent {response.success_count} messages.")
    if response.failure_count > 0:
        responses = response.responses
        failed_tokens = []
        for idx, resp in enumerate(responses):
            if not resp.success:
                # The order of responses corresponds to the order of the registration tokens.
                failed_tokens.append(tokens[idx])
        print(f"[PUSH] List of tokens that caused failures: {failed_tokens}")
        # In a real app, remove invalid tokens here
  except Exception as e:
    print(f"[PUSH] Error sending message: {e}")


def send_notification(method, reminder_data, user_data, devotion_url):
  """Sends a notification via the specified method."""
  devotion_name = DEVOTION_NAMES.get(reminder_data.get("devotion"))
  message = f"Time for {devotion_name}! Read here: {devotion_url}"

  if method == "push":
    _send_push(user_data, "Prayer Reminder", message, devotion_url)


def send_due_reminders():
  """Checks for reminders due at the current time and sends them."""
  print("Checking for due prayer reminders...")
  db = utils.get_db_client()
  now_utc = datetime.datetime.now(datetime.timezone.utc)

  # Collection Group Query
  # Requires a composite index in Firestore for 'reminders' collection group on 'next_run_utc' ASC
  query = db.collection_group(REMINDERS_COLLECTION).where(
      "next_run_utc", "<=", now_utc
  )

  docs = list(query.stream())
  print(f"Found {len(docs)} due reminders.")

  for doc in docs:
    data = doc.to_dict()
    methods = data.get("methods", [])
    devotion_key = data.get("devotion")
    user_id = data.get("user_id")

    # Fetch user data for contact info
    user_doc = db.collection("users").document(user_id).get()
    if not user_doc.exists:
      print(f"User {user_id} not found, skipping reminder {doc.id}")
      continue
    user_data = user_doc.to_dict()

    base_url = "https://www.lcmsprayer.com"
    devotion_path = DEVOTION_URLS.get(devotion_key, "/")
    full_url = f"{base_url}{devotion_path}"

    for method in methods:
      try:
        send_notification(method, data, user_data, full_url)
      except Exception as e:
        print(f"Error sending {method} notification for reminder {doc.id}: {e}")

    # Schedule next run
    try:
      # Calculate next run from the *scheduled* time to avoid drift,
      # or from now if we want to reset base.
      # Better to recalculate from "now" to ensure it's in the future.
      next_run = calculate_next_run(data.get("time"), data.get("timezone"))
      doc.reference.update({"next_run_utc": next_run})
    except Exception as e:
      print(f"Error rescheduling reminder {doc.id}: {e}")

  return True
