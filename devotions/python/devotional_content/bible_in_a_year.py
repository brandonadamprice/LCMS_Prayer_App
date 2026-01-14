"""Functions for generating the Bible in a Year page."""

import json
import os
import flask
import utils

BIBLE_IN_A_YEAR_JSON_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "bible_in_a_year.json"
)


def load_bible_in_a_year_data():
  """Loads Bible in a Year data from JSON file."""
  with open(BIBLE_IN_A_YEAR_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def save_bia_progress(user_id: str, day: int, last_visit_str: str):
  """Saves Bible in a Year progress for a user."""
  db = utils.get_db_client()
  user_ref = db.collection("users").document(user_id)
  user_ref.set(
      {"bia_progress": {"current_day": day, "last_visit_str": last_visit_str}},
      merge=True,
  )


def get_bible_in_a_year_devotion_data(user_id=None):
  """Generates data for the Bible in a Year devotion for email/reminders."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  bible_in_a_year_data = load_bible_in_a_year_data()

  current_day = now.timetuple().tm_yday  # Default to day of year

  if user_id:
    db = utils.get_db_client()
    doc = db.collection("users").document(user_id).get()
    if doc.exists:
      bia_progress = doc.to_dict().get("bia_progress")
      if bia_progress and "current_day" in bia_progress:
        # If they have a progress, use it.
        # Note: The web UI advances day automatically if last_visit < today.
        # For email, we probably want to send the "next" reading if they finished yesterday?
        # Or just send the one they are currently on.
        # Let's stick to what the UI would load: the stored current_day.
        # If they read it today, it might be the same one.
        # Complex logic, let's just use stored day.
        current_day = int(bia_progress["current_day"])

  # Ensure day is within range 1-365
  current_day = max(1, min(current_day, 365))

  day_data = bible_in_a_year_data[current_day - 1]

  ot_ref = day_data["Old Testament"]
  nt_ref = day_data["New Testament"]
  psp_ref = day_data["Psalms & Proverbs"]

  try:
    texts = utils.fetch_passages([ot_ref, nt_ref, psp_ref])
    ot_text = texts[0]
    nt_text = texts[1]
    psp_text = texts[2]
  except Exception as e:
    print(f"Error fetching passages for Bible in a Year: {e}")
    ot_text = "Text not available"
    nt_text = "Text not available"
    psp_text = "Text not available"

  return {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "day_number": current_day,
      "ot_ref": ot_ref,
      "ot_text": ot_text,
      "nt_ref": nt_ref,
      "nt_text": nt_text,
      "psp_ref": psp_ref,
      "psp_text": psp_text,
  }


def generate_bible_in_a_year_page(bia_progress=None):
  """Generates HTML for the Bible in a Year page."""
  bible_in_a_year_data = load_bible_in_a_year_data()

  # Pass all schedule data to the template.
  # The client-side JavaScript will handle day progression
  # and fetching readings via /get_passage_text.

  template_data = {
      "schedule": json.dumps(bible_in_a_year_data),
      "bia_progress": json.dumps(bia_progress) if bia_progress else "null",
  }

  print("Generated Bible in a Year HTML")
  return flask.render_template("bible_in_a_year.html", **template_data)
