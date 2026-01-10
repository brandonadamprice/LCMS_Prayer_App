"""Functions for generating the midday devotion."""

import datetime
import flask
import pytz
import utils


def get_midday_devotion_data(user_id=None):
  """Generates data for the midday devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  cy = utils.ChurchYear(now.year)
  key = cy.get_liturgical_key(now)

  reading_ref = utils.get_deterministic_choice(
      utils.OFFICE_READINGS["midday_readings"], now
  )
  psalm_options = utils.OFFICE_READINGS.get("midday_psalms", [])
  psalm_ref = utils.get_deterministic_choice(psalm_options, now)

  # Daily Lectionary
  lectionary_data = utils.load_lectionary(utils.LECTIONARY_JSON_PATH)
  l_readings = lectionary_data.get(
      key, {"OT": "Reading not found", "NT": "Reading not found"}
  )
  daily_lectionary_readings = [
      r
      for r in [l_readings["OT"], l_readings["NT"]]
      if r != "Reading not found"
  ]

  all_refs = [reading_ref, psalm_ref] + daily_lectionary_readings
  all_texts = utils.fetch_passages(all_refs)
  reading_text = all_texts[0]
  psalm_text = all_texts[1]
  lectionary_texts = all_texts[2:]

  concluding_prayer = utils.OTHER_PRAYERS["midday_prayers"]
  all_personal_prayers = utils.get_all_personal_prayers_for_user(user_id)

  return {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "daily_lectionary_readings": daily_lectionary_readings,
      "lectionary_texts": lectionary_texts,
      "key": key,
      "reading_ref": reading_ref,
      "reading_options": utils.OFFICE_READINGS["midday_readings"],
      "reading_text": reading_text,
      "psalm_ref": psalm_ref,
      "psalm_options": psalm_options,
      "psalm_text": psalm_text,
      "concluding_prayer": concluding_prayer,
      "all_personal_prayers": all_personal_prayers,
  }


def generate_midday_devotion():
  """Generates HTML for the midday devotion for the current date."""
  template_data = get_midday_devotion_data()
  print("Generated Midday HTML")
  return flask.render_template("midday_devotion.html", **template_data)
