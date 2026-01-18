"""Functions for generating the Night Watch devotion."""

import datetime
from devotional_content import bible_in_a_year
import flask
import pytz
import utils


def get_night_watch_devotion_data(user_id=None):
  """Generates data for the Night Watch devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  psalm_ref = utils.get_deterministic_choice(
      utils.OFFICE_READINGS["night_watch_psalms"], now
  )
  reading_ref = utils.get_deterministic_choice(
      utils.OFFICE_READINGS["night_watch_readings"], now
  )
  # Daily Lectionary
  lectionary_data = utils.load_lectionary(utils.LECTIONARY_JSON_PATH)
  # Night Watch uses specific readings too, but user asked for "nightwatch devotional" too.
  # We use the same daily lectionary lookup.
  key = utils.ChurchYear(now.year).get_liturgical_key(now)
  l_readings = lectionary_data.get(
      key, {"OT": "Reading not found", "NT": "Reading not found"}
  )
  daily_lectionary_readings = [
      r
      for r in [l_readings["OT"], l_readings["NT"]]
      if r != "Reading not found"
  ]

  # Bible in a Year
  bible_in_a_year_data = bible_in_a_year.get_bible_in_a_year_devotion_data(
      user_id
  )

  all_refs = [psalm_ref, reading_ref] + daily_lectionary_readings
  all_texts = utils.fetch_passages(all_refs)
  psalm_text = all_texts[0]
  reading_text = all_texts[1]
  lectionary_texts = all_texts[2:]

  protection_prayer = utils.OTHER_PRAYERS["night_watch_protection_prayers"]
  concluding_prayer = utils.OTHER_PRAYERS["night_watch_concluding_prayers"]

  return {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "daily_lectionary_readings": daily_lectionary_readings,
      "lectionary_texts": lectionary_texts,
      "bible_in_a_year_reading": bible_in_a_year_data,
      "psalm_ref": psalm_ref,
      "psalm_text": psalm_text,
      "psalm_options": utils.OFFICE_READINGS["night_watch_psalms"],
      "reading_ref": reading_ref,
      "reading_text": reading_text,
      "reading_options": utils.OFFICE_READINGS["night_watch_readings"],
      "protection_prayer": protection_prayer,
      "concluding_prayer": concluding_prayer,
  }


def generate_night_watch_devotion():
  """Generates HTML for the Night Watch devotion."""
  template_data = get_night_watch_devotion_data()
  print("Generated Night Watch HTML")
  return flask.render_template("night_watch_devotion.html", **template_data)
