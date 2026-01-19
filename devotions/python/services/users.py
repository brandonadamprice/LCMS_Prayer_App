"""Functions for managing users, authentication, and streaks."""

import datetime
import logging
import re
import uuid

import communication
import flask
from google.cloud import firestore
from itsdangerous import URLSafeTimedSerializer
import models
import pytz
import utils

logger = logging.getLogger(__name__)


def get_user_by_email(email):
  """Finds a user by email."""
  db = utils.get_db_client()
  users_ref = db.collection("users")
  query = users_ref.where("email", "==", email).limit(1)
  results = list(query.stream())
  if results:
    return models.User.get(results[0].id)
  return None


def get_reset_token(email):
  """Generates a password reset token."""
  serializer = URLSafeTimedSerializer(utils.secrets.get_flask_secret_key())
  return serializer.dumps(email, salt="password-reset-salt")


def verify_reset_token(token, expiration=1800):
  """Verifies a password reset token."""
  serializer = URLSafeTimedSerializer(utils.secrets.get_flask_secret_key())
  try:
    email = serializer.loads(
        token, salt="password-reset-salt", max_age=expiration
    )
  except Exception:
    return None
  return email


def send_password_reset_email(email, reset_link):
  """Sends a password reset email."""
  body = (
      f"To reset your password, visit the following link: {reset_link}\n\n"
      "This link will expire in 30 minutes.\n\n"
      "If you did not make this request then simply ignore this email and no"
      " changes will be made."
  )
  success = communication.send_email(
      email, "Password Reset Request", body_text=body
  )

  if not success:
    logger.warning("Email sending failed for password reset to %s", email)
    logger.info("Reset Link: %s", reset_link)

  return True


def reset_password(email, new_password_hash):
  """Resets the user's password."""
  user = get_user_by_email(email)
  if not user:
    return False

  db = utils.get_db_client()
  db.collection("users").document(user.id).update(
      {"password_hash": new_password_hash}
  )
  return True


def get_completion_token(user_id, devotion_type, date_str, bible_year_day=None):
  """Generates a token for marking a prayer as complete."""
  serializer = URLSafeTimedSerializer(utils.secrets.get_flask_secret_key())
  data = {"uid": user_id, "dt": devotion_type, "d": date_str}
  if bible_year_day:
    data["byd"] = bible_year_day
  return serializer.dumps(data, salt="prayer-completion-salt")


def verify_completion_token(token, expiration=86400 * 2):
  """Verifies a prayer completion token (valid for 2 days)."""
  serializer = URLSafeTimedSerializer(utils.secrets.get_flask_secret_key())
  try:
    data = serializer.loads(
        token, salt="prayer-completion-salt", max_age=expiration
    )
    return data
  except Exception:
    return None


def validate_password(password):
  """Checks password complexity."""
  if len(password) < 8:
    return "Password must be at least 8 characters long."
  if not re.search(r"[A-Z]", password):
    return "Password must contain at least one capital letter."
  if not re.search(r"[^a-zA-Z]", password):
    return "Password must contain at least one number or symbol."
  return None


def validate_email(email):
  """Checks if email format is valid."""
  if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
    return "Invalid email address format."
  return None


def send_verification_email(email, code):
  """Sends a verification email using SMTP."""
  body = f"Your verification code for A Simple Way to Pray is: {code}"
  success = communication.send_email(
      email, "Your Verification Code", body_text=body
  )

  if not success:
    # If sending failed (e.g. no credentials in dev), log the code.
    logger.warning("Email sending failed. Logging verification code.")
    logger.info("========== EMAIL VERIFICATION ==========")
    logger.info("To: %s", email)
    logger.info("Code: %s", code)
    logger.info("========================================")
    return True

  return success


def get_oauth_user_data(user_info, provider):
  """Extracts standard user data from OAuth info."""
  data = {}
  if provider == "google":
    data["google_id"] = user_info["sub"]
    data["email"] = user_info.get("email", "").lower()
    data["name"] = user_info.get("name")
    data["profile_pic"] = user_info.get("picture")
    data["google_profile_pic"] = user_info.get("picture")
  return data


def create_new_user_doc(user_data, provider):
  """Creates a new user document."""
  db = utils.get_db_client()
  if provider == "google":
    # Maintain backward compatibility: Google users use sub as doc ID
    user_id = user_data["google_id"]
  elif provider == "email":
    # For email users, generate a unique ID
    user_id = str(uuid.uuid4())
  else:
    # Prefix others to avoid collision if IDs overlap (unlikely but safe)
    user_id = f"{provider}_{user_data[f'{provider}_id']}"

  user_data["last_login"] = datetime.datetime.now(datetime.timezone.utc)
  db.collection("users").document(user_id).set(user_data, merge=True)
  return models.User.get(user_id)


def update_existing_user_doc(user_id, user_data):
  """Updates an existing user document."""
  db = utils.get_db_client()
  user_data["last_login"] = datetime.datetime.now(datetime.timezone.utc)

  # If user has explicitly selected a source, don't overwrite the main profile_pic
  # with the one from this login, unless it's the same source.
  # However, we DO want to update google_profile_pic/facebook_profile_pic.

  user_ref = db.collection("users").document(user_id)
  current_doc = user_ref.get()
  if current_doc.exists:
    current_data = current_doc.to_dict()
    selected_source = current_data.get("selected_pic_source")

    # If a specific source is selected and it's not the current provider (implied by this login),
    # keep the existing profile_pic.
    # Note: user_data['profile_pic'] currently holds the provider's pic.

    if selected_source and selected_source != "provider_default":
      # We are updating from a login.
      # If the user has a custom selection, or a selection from a different provider,
      # we might want to preserve the *current* main profile_pic.
      # But we definitely want to update the provider-specific field.

      # Let's just remove 'profile_pic' from user_data so it doesn't overwrite
      # the existing one in the set(merge=True) call.
      # Exception: if the selected source IS this provider (e.g. they selected 'google'
      # and are logging in with google), we should update it to the latest.

      # Since we don't easily know "which provider" called this function without parsing user_data keys,
      # we can check:
      is_google = "google_profile_pic" in user_data

      if selected_source == "google" and is_google:
        pass  # Let it update
      elif selected_source == "custom":
        if "profile_pic" in user_data:
          del user_data["profile_pic"]
      elif selected_source == "google" and not is_google:
        if "profile_pic" in user_data:
          del user_data["profile_pic"]

  db.collection("users").document(user_id).set(user_data, merge=True)
  return models.User.get(user_id)


def handle_oauth_login(user_info, provider):
  """Handles the login logic including merge detection."""
  user_data = get_oauth_user_data(user_info, provider)
  email = user_data.get("email")
  provider_id_field = f"{provider}_id"
  provider_id_value = user_data[provider_id_field]

  db = utils.get_db_client()
  users_ref = db.collection("users")

  # 1. Check if user exists by this provider ID
  query = users_ref.where(provider_id_field, "==", provider_id_value).limit(1)
  results = list(query.stream())

  if results:
    # Found existing linked user
    user_doc = results[0]
    return update_existing_user_doc(user_doc.id, user_data)

  # 2. Check by email for merge opportunity
  if email:
    query_email = users_ref.where("email", "==", email).limit(1)
    email_results = list(query_email.stream())
    if email_results:
      # Found conflict/merge opportunity
      # Store info in session and redirect to merge prompt
      # We return a special signal (None, redirect_url)
      flask.session["pending_user_data"] = user_data
      flask.session["pending_provider"] = provider
      return None

  # 3. New user
  return create_new_user_doc(user_data, provider)


def process_prayer_completion(
    user_id, devotion_type, timezone_str, bible_year_day=None
):
  """Marks a prayer as complete and updates the streak."""
  try:
    tz = pytz.timezone(timezone_str)
  except pytz.UnknownTimeZoneError:
    tz = pytz.timezone("America/New_York")

  now = datetime.datetime.now(tz)
  today_str = now.strftime(
      "%Y-%m-%d"
  )  # YYYY-MM-DD format for storage consistency
  now_iso = now.isoformat()

  # If Bible in a Year reading was included, mark it as complete too.
  # We do this outside the prayer streak transaction to avoid complexity,
  # or we could do it serially. Since they affect different fields/logic
  # (and process_bible_reading_completion is its own transactional function),
  # calling it here is fine.
  bible_res = {}
  if bible_year_day:
    try:
      # Ensure bible_year_day is int
      day_num = int(bible_year_day)
      bible_res = process_bible_reading_completion(
          user_id, day_num, timezone_str
      )
    except Exception as e:
      logger.error(f"Failed to mark bible reading complete: {e}")

  db = utils.get_db_client()
  user_ref = db.collection("users").document(user_id)

  # Transaction to safely update streak
  @firestore.transactional
  def update_streak_in_transaction(transaction, user_ref):
    snapshot = next(transaction.get(user_ref))
    if not snapshot.exists:
      return None

    user_data = snapshot.to_dict()
    current_streak = user_data.get("streak_count", 0)
    best_streak = user_data.get("best_streak_count", 0)
    current_achievements = user_data.get("achievements", [])
    completed_devotions = user_data.get("completed_devotions", {})
    last_date_str = user_data.get(
        "last_prayer_date"
    )  # Expecting string YYYY-MM-DD

    # Parse last_date if it exists
    last_date = None
    if last_date_str:
      try:
        last_date = datetime.datetime.strptime(last_date_str, "%Y-%m-%d").date()
      except ValueError:
        # Handle legacy or bad format if necessary, reset
        pass

    today_date = now.date()

    # Update completed devotions for today
    completed_devotions[devotion_type] = now_iso

    # Calculate how many distinct devotions done TODAY
    devotions_today_count = 0
    for _, ts_str in completed_devotions.items():
      try:
        # Simple check: Does the date part match today_str?
        if ts_str.startswith(today_str):
          devotions_today_count += 1
      except ValueError:
        pass

    new_streak = current_streak
    streak_updated = False

    # Only update streak if it hasn't been updated today
    # But we ALWAYS update 'completed_devotions' and 'last_prayer_date'
    if last_date == today_date:
      # Already prayed today, streak stays same
      streak_updated = False  # Streak count doesn't change
    elif last_date == today_date - datetime.timedelta(days=1):
      # Prayed yesterday, increment
      new_streak += 1
      streak_updated = True
    else:
      # Missed a day or more (or first time)
      new_streak = 1
      streak_updated = True
    
    if new_streak > best_streak:
        best_streak = new_streak

    # Check for milestones/achievements
    milestone_reached = False
    milestone_msg = ""
    new_achievements = []

    milestone_map = {
        7: ("1 Week Streak", "🔥"),
        30: ("1 Month Streak", "🎗️"),
        90: ("3 Months Streak", "🥉"),
        180: ("6 Months Streak", "🥈"),
        270: ("9 Months Streak", "🥇"),
        365: ("1 Year Streak", "🏆"),
    }

    # Helper to add achievement if not present
    def check_and_add(streak_val, title, icon="🔥"):
      nonlocal milestone_reached, milestone_msg
      # Create a slug/id for the achievement
      ach_id = f"streak_{streak_val}"
      # Check if user already has it
      if not any(a["id"] == ach_id for a in current_achievements):
        # New achievement!
        new_achievements.append({
            "id": ach_id,
            "title": title,
            "date": today_str,
            "icon": icon,
        })
        milestone_reached = True
        milestone_msg = f"Achievement Unlocked: {title}!"

    # Check standard milestones
    for day_count, (title, icon) in milestone_map.items():
      if day_count <= new_streak:
        check_and_add(day_count, title, icon)

    # Check periodic milestones > 365
    if new_streak > 365 and (new_streak - 365) % 90 == 0:
      # Dynamic title
      title = f"{new_streak} Day Streak"
      # Only add if it's the exact day we crossed it
      if streak_updated:  # Wait, logic above was: if streak_val <= new_streak.
        # We want to only trigger if we *just* reached it.
        # Since we only increment by 1, <= is effectively == if we haven't seen it before.
        check_and_add(new_streak, title, "👑")

    # Check Daily Office Achievement
    # Requirements: morning, midday, evening, close_of_day done TODAY
    required_offices = ["morning", "midday", "evening", "close_of_day"]
    daily_office_done = True
    for office in required_offices:
      ts_str = completed_devotions.get(office)
      if not ts_str or not ts_str.startswith(today_str):
        daily_office_done = False
        break

    if daily_office_done:
      ach_id = f"daily_office_{today_str}"
      title = "Daily Office Completed"
      if not any(a["id"] == ach_id for a in current_achievements):
        new_achievements.append({
            "id": ach_id,
            "title": title,
            "date": today_str,
            "icon": "📖",
        })
        # Priority to this msg if other milestones not reached, or append
        if not milestone_reached:
          milestone_reached = True
          milestone_msg = "Achievement Unlocked: Daily Office!"

    # Construct response message
    response_msg = ""
    if streak_updated:
      response_msg = f"Prayer recorded! Current Streak: {new_streak} days"
    else:
      response_msg = f"You've already prayed today! Streak: {new_streak}"

    if devotions_today_count > 1:
      response_msg += (
          f". You have completed {devotions_today_count} devotions today!"
      )

    # Apply updates
    update_data = {
        "completed_devotions": completed_devotions,
        "last_prayer_date": today_str,  # Always update last date to today
        "best_streak_count": best_streak,
    }
    if streak_updated:
      update_data["streak_count"] = new_streak

    if new_achievements:
      all_achievements = current_achievements + new_achievements
      update_data["achievements"] = all_achievements

    transaction.update(user_ref, update_data)

    result = {
        "streak": new_streak,
        "milestone_reached": milestone_reached,
        "milestone_msg": milestone_msg,
        "already_prayed": not streak_updated,
        "devotions_today_count": devotions_today_count,
        "message": response_msg,
    }

    # Merge bible results if any
    if bible_res:
      result["bible_streak"] = bible_res.get("bible_streak")
      result["bible_milestone_reached"] = bible_res.get("milestone_reached")
      if bible_res.get("milestone_reached"):
        # Combine messages if both reached?
        if result["milestone_reached"]:
          result["milestone_msg"] += (
              f" Also: {bible_res.get('milestone_msg')}"
          )
        else:
          result["milestone_reached"] = True
          result["milestone_msg"] = bible_res.get("milestone_msg")

    return result

  transaction = db.transaction()
  return update_streak_in_transaction(transaction, user_ref)


def process_bible_reading_completion(user_id, day_number, timezone_str):
  """Marks a Bible reading as complete and updates the Bible streak."""
  try:
    tz = pytz.timezone(timezone_str)
  except pytz.UnknownTimeZoneError:
    tz = pytz.timezone("America/New_York")

  now = datetime.datetime.now(tz)
  today_str = now.strftime("%Y-%m-%d")
  
  db = utils.get_db_client()
  user_ref = db.collection("users").document(user_id)

  @firestore.transactional
  def update_bible_streak_in_transaction(transaction, user_ref):
    snapshot = next(transaction.get(user_ref))
    if not snapshot.exists:
      return None

    user_data = snapshot.to_dict()
    current_bible_streak = user_data.get("bible_streak_count", 0)
    best_bible_streak = user_data.get("best_bible_streak_count", 0)
    current_achievements = user_data.get("achievements", [])
    completed_bible_days = user_data.get("completed_bible_days", [])
    last_bible_date_str = user_data.get("last_bible_reading_date")

    # Update completed days
    if day_number not in completed_bible_days:
      completed_bible_days.append(day_number)
      completed_bible_days.sort()

    last_bible_date = None
    if last_bible_date_str:
      try:
        last_bible_date = datetime.datetime.strptime(
            last_bible_date_str, "%Y-%m-%d"
        ).date()
      except ValueError:
        pass

    today_date = now.date()
    new_bible_streak = current_bible_streak
    streak_updated = False

    if last_bible_date == today_date:
      streak_updated = False
    elif last_bible_date == today_date - datetime.timedelta(days=1):
      new_bible_streak += 1
      streak_updated = True
    else:
      new_bible_streak = 1
      streak_updated = True
      
    if new_bible_streak > best_bible_streak:
        best_bible_streak = new_bible_streak

    # Achievements
    new_achievements = []
    milestone_reached = False
    milestone_msg = ""

    # Helper to add achievement
    def check_and_add(ach_id, title, icon):
      nonlocal milestone_reached, milestone_msg
      if not any(a["id"] == ach_id for a in current_achievements):
        new_achievements.append({
            "id": ach_id,
            "title": title,
            "date": today_str,
            "icon": icon,
        })
        milestone_reached = True
        milestone_msg = f"Achievement Unlocked: {title}!"

    # Streak Milestones
    streak_milestones = {
        7: ("1 Week Bible Streak", "📚"),
        30: ("1 Month Bible Streak", "🕯️"),
        90: ("3 Months Bible Streak", "📜"),
        180: ("6 Months Bible Streak", "🏛️"),
        365: ("1 Year Bible Streak", "⛪"),
    }

    for days, (title, icon) in streak_milestones.items():
      if days <= new_bible_streak:
        check_and_add(f"bible_streak_{days}", title, icon)

    # Progress Milestones (Total 365 days)
    total_completed = len(completed_bible_days)
    progress_pct = (total_completed / 365) * 100

    if progress_pct >= 25:
      check_and_add("bible_25_percent", "25% Bible Completed", "🌱")
    if progress_pct >= 50:
      check_and_add("bible_50_percent", "50% Bible Completed", "🌿")
    if progress_pct >= 75:
      check_and_add("bible_75_percent", "75% Bible Completed", "🌳")
    if total_completed >= 365:
      check_and_add("bible_100_percent", "Bible in a Year Completed", "👑")

    # Update Data
    update_data = {
        "completed_bible_days": completed_bible_days,
        "last_bible_reading_date": today_str,
        "bia_progress": { # Sync with old tracking for continuity
            "current_day": day_number,
            "last_visit_str": today_str
        },
        "best_bible_streak_count": best_bible_streak,
    }
    if streak_updated:
      update_data["bible_streak_count"] = new_bible_streak
    
    if new_achievements:
      update_data["achievements"] = current_achievements + new_achievements

    transaction.update(user_ref, update_data)

    return {
        "bible_streak": new_bible_streak,
        "total_completed": total_completed,
        "milestone_reached": milestone_reached,
        "milestone_msg": milestone_msg,
        "progress_pct": progress_pct
    }

  transaction = db.transaction()
  return update_bible_streak_in_transaction(transaction, user_ref)


def mark_bible_days_completed(user_id, days):
  """Marks specific Bible days as completed in bulk."""
  db = utils.get_db_client()
  user_ref = db.collection("users").document(user_id)

  @firestore.transactional
  def update_bulk_transaction(transaction, user_ref):
    snapshot = next(transaction.get(user_ref))
    if not snapshot.exists:
      return None

    user_data = snapshot.to_dict()
    completed_bible_days = user_data.get("completed_bible_days", [])
    current_achievements = user_data.get("achievements", [])

    # Add new days
    updated = False
    for day in days:
      if day not in completed_bible_days:
        completed_bible_days.append(day)
        updated = True

    if not updated:
      return {"message": "No new days to mark."}

    completed_bible_days.sort()

    # Check Progress Milestones (Total 365 days)
    new_achievements = []
    # Use timezone aware now if possible, or just UTC for achievements date
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    def check_and_add(ach_id, title, icon):
      if not any(a["id"] == ach_id for a in current_achievements):
        new_achievements.append({
            "id": ach_id,
            "title": title,
            "date": today_str,
            "icon": icon,
        })

    total_completed = len(completed_bible_days)
    progress_pct = (total_completed / 365) * 100

    if progress_pct >= 25:
      check_and_add("bible_25_percent", "25% Bible Completed", "🌱")
    if progress_pct >= 50:
      check_and_add("bible_50_percent", "50% Bible Completed", "🌿")
    if progress_pct >= 75:
      check_and_add("bible_75_percent", "75% Bible Completed", "🌳")
    if total_completed >= 365:
      check_and_add("bible_100_percent", "Bible in a Year Completed", "👑")

    update_data = {"completed_bible_days": completed_bible_days}
    if new_achievements:
      update_data["achievements"] = current_achievements + new_achievements

    transaction.update(user_ref, update_data)
    return {
        "success": True,
        "total_completed": total_completed,
        "new_achievements": len(new_achievements),
    }

  transaction = db.transaction()
  return update_bulk_transaction(transaction, user_ref)
