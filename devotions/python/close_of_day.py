"""Functions for generating the close of day devotion."""

import datetime
import random
import flask
import pytz
import utils


def get_close_of_day_devotion_data(user_id=None):
  """Generates data for the close of day devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  cy = utils.ChurchYear(now.year)
  key = cy.get_liturgical_key(now)

  reading_ref = random.choice(utils.OFFICE_READINGS["close_of_day_readings"])
  psalm_options = utils.OFFICE_READINGS.get("close_of_day_psalms", [])
  psalm_ref = random.choice(psalm_options)

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

  weekly_prayer_data = utils.get_weekly_prayer_for_day(now, user_id)
  concluding_prayer = utils.OTHER_PRAYERS["close_of_day_prayers"]

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "daily_lectionary_readings": daily_lectionary_readings,
      "lectionary_texts": lectionary_texts,
      "key": key,
      "psalm_ref": psalm_ref,
      "psalm_options": psalm_options,
      "psalm_text": psalm_text,
      "reading_ref": reading_ref,
      "reading_options": utils.OFFICE_READINGS["close_of_day_readings"],
      "reading_text": reading_text,
      "concluding_prayer": concluding_prayer,
      "luthers_evening_prayer": utils.OTHER_PRAYERS["luthers_evening_prayer"],
  }
  template_data.update(weekly_prayer_data)
  return template_data


def generate_close_of_day_devotion():
  """Generates HTML for the close of day devotion for the current date."""
  template_data = get_close_of_day_devotion_data()
  print("Generated Close of Day HTML")
  return flask.render_template("close_of_day_devotion.html", **template_data)
