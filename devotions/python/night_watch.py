"""Functions for generating the Night Watch devotion."""

import datetime
import random
import flask
import pytz
import utils


def generate_night_watch_devotion():
  """Generates HTML for the Night Watch devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  psalm_ref = random.choice(utils.OFFICE_READINGS["night_watch_psalms"])
  reading_ref = random.choice(utils.OFFICE_READINGS["night_watch_readings"])
  psalm_text, reading_text = utils.fetch_passages([psalm_ref, reading_ref])
  protection_prayer = utils.OTHER_PRAYERS["night_watch_protection_prayers"]
  concluding_prayer = utils.OTHER_PRAYERS["night_watch_concluding_prayers"]

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

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "daily_lectionary_readings": daily_lectionary_readings,
      "psalm_ref": psalm_ref,
      "psalm_text": psalm_text,
      "psalm_options": utils.OFFICE_READINGS["night_watch_psalms"],
      "reading_ref": reading_ref,
      "reading_text": reading_text,
      "reading_options": utils.OFFICE_READINGS["night_watch_readings"],
      "protection_prayer": protection_prayer,
      "concluding_prayer": concluding_prayer,
  }
  print("Generated Night Watch HTML")
  return flask.render_template("night_watch_devotion.html", **template_data)
