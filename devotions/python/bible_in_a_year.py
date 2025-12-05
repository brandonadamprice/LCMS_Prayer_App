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
  return flask.render_template(
      "bible_in_a_year.html", **template_data
  )
