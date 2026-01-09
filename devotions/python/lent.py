"""Functions for generating the Lenten devotion."""

import datetime
import json
import os
import flask
import pytz
import utils

LENT_JSON_PATH = os.path.join(utils.SCRIPT_DIR, "..", "data", "lent.json")


def load_lent_devotions():
  """Loads Lenten devotions from JSON file."""
  with open(LENT_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def generate_lent_devotion():
  """Generates HTML for the Lenten devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  today = now.date()

  cy = utils.ChurchYear(today.year)
  ash_wednesday = cy.ash_wednesday
  easter_sunday = cy.easter_date

  # Check if it is Lent (should be handled by caller too, but good for safety)
  if not (ash_wednesday <= today <= easter_sunday):
    # Fallback or redirect if accessed out of season?
    # For now, let's just calculate the offset.
    # If we are testing, we might want to see it even if out of season.
    pass

  day_offset = (today - ash_wednesday).days

  lent_devotions = load_lent_devotions()

  # Safe retrieval
  if 0 <= day_offset < len(lent_devotions):
    devotion_data = lent_devotions[day_offset]
  else:
    # Fallback to the first one or a generic one if data is missing
    devotion_data = lent_devotions[0] if lent_devotions else {}

  ot_ref = devotion_data.get("OT_ref", "Joel 2:12-19")
  nt_ref = devotion_data.get("NT_ref", "Matthew 6:16-21")

  try:
    reading_texts = utils.fetch_passages([ot_ref, nt_ref])
    ot_text = reading_texts[0]
    nt_text = reading_texts[1]
  except Exception as e:
    print(f"Error fetching passage: {e}")
    ot_text = "Reading text not available."
    nt_text = "Reading text not available."

  meditation_html = (
      f'<p>{devotion_data.get("meditation", "Meditation not available.")}</p>'
  )
  prayer_html = f'<p>{devotion_data.get("prayer", "Prayer not available.")}</p>'

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "devotion_title": devotion_data.get("title", "Lenten Devotion"),
      "ot_ref": ot_ref,
      "ot_text": ot_text,
      "nt_ref": nt_ref,
      "nt_text": nt_text,
      "meditation_html": meditation_html,
      "prayer_html": prayer_html,
  }

  print("Generated Lent HTML")
  return flask.render_template("lent_devotion.html", **template_data)
