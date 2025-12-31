"""Functions for generating the close of day devotion."""

import datetime
import random
import flask
import pytz
import utils


def generate_close_of_day_devotion():
  """Generates HTML for the close of day devotion for the current date."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  cy = utils.ChurchYear(now.year)
  key = cy.get_liturgical_key(now)

  reading_ref = random.choice(utils.OFFICE_READINGS["close_of_day_readings"])
  psalm_options = utils.OFFICE_READINGS.get("close_of_day_psalms", [])
  psalm_ref = random.choice(psalm_options)

  reading_text, psalm_text = utils.fetch_passages([reading_ref, psalm_ref])

  weekly_prayer_data = utils.get_weekly_prayer_for_day(now)
  concluding_prayer = utils.OTHER_PRAYERS["close_of_day_prayers"]

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
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
  print("Generated Close of Day HTML")
  return flask.render_template("close_of_day_devotion.html", **template_data)
