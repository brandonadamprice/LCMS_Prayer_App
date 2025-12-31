"""Functions for generating the evening devotion."""

import datetime
import random
import flask
import pytz
import utils


def generate_evening_devotion():
  """Generates HTML for the evening devotion for the current date."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  cy = utils.ChurchYear(now.year)
  key = cy.get_liturgical_key(now)
  catechism_data = utils.get_catechism_for_day(now, rotation="daily")

  reading_ref = random.choice(utils.OFFICE_READINGS["evening_readings"])
  psalm_options = utils.OFFICE_READINGS.get("evening_psalms", [])
  psalm_ref = random.choice(psalm_options)

  reading_text, psalm_text = utils.fetch_passages([reading_ref, psalm_ref])
  concluding_prayer = utils.OTHER_PRAYERS["evening_prayers"]
  all_personal_prayers = utils.get_all_personal_prayers_for_user()

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

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "daily_lectionary_readings": daily_lectionary_readings,
      "key": key,
      "reading_ref": reading_ref,
      "reading_options": utils.OFFICE_READINGS["evening_readings"],
      "reading_text": reading_text,
      "psalm_ref": psalm_ref,
      "psalm_options": psalm_options,
      "psalm_text": psalm_text,
      "concluding_prayer": concluding_prayer,
      "all_personal_prayers": all_personal_prayers,
  }
  template_data.update(catechism_data)

  print("Generated Evening HTML")
  return flask.render_template("evening_devotion.html", **template_data)
