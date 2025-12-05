"""Book of Concord in a Year devotional."""

import datetime
import json
import os
import flask
import utils

BOC_JSON_PATH = os.path.join(utils.DATA_DIR, "boc_in_a_year.json")
BOC_READINGS = []


def _load_readings():
  """Loads BOC readings from JSON file."""
  global BOC_READINGS
  if not BOC_READINGS:
    try:
      with open(BOC_JSON_PATH, "r", encoding="utf-8") as f:
        BOC_READINGS = json.load(f)
    except FileNotFoundError:
      print(f"Error: {BOC_JSON_PATH} not found.")
      BOC_READINGS = []


def get_boc_readings():
  _load_readings()
  return BOC_READINGS


def save_boc_progress(user_id: str, day: int, date_str: str):
  """Saves BOC progress to Firestore."""
  db = utils.get_db_client()
  user_ref = db.collection("users").document(user_id)
  user_ref.set({"boc_progress": {"day": day, "last_visit": date_str}}, merge=True)


def generate_boc_page(boc_progress=None):
  """Generates the BOC in a Year page with progress."""
  readings = get_boc_readings()
  today = datetime.datetime.now()
  day_of_year = today.timetuple().tm_yday
  today_reading_index = (day_of_year - 1) % len(readings) if readings else -1

  return flask.render_template(
      "boc_year.html",
      readings=readings,
      progress=boc_progress,
      today_reading_index=today_reading_index,
  )
