"""Functions for generating the morning devotion."""

import datetime
import random
import flask
import pytz
import utils


def generate_morning_devotion():
  """Generates HTML for the morning devotion for the current date."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  cy = utils.ChurchYear(now.year)
  key = cy.get_liturgical_key(now)

  reading_ref = random.choice(utils.OFFICE_READINGS["morning_readings"])
  psalm_options = utils.OFFICE_READINGS.get("morning_psalms", [])
  psalm_ref = random.choice(psalm_options)

  reading_text, psalm_text = utils.fetch_passages([reading_ref, psalm_ref])
  concluding_prayer = utils.OTHER_PRAYERS["morning_prayers"]
  all_personal_prayers = utils.get_all_personal_prayers_for_user()

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "key": key,
      "reading_ref": reading_ref,
      "reading_options": utils.OFFICE_READINGS["morning_readings"],
      "reading_text": reading_text,
      "psalm_ref": psalm_ref,
      "psalm_options": psalm_options,
      "psalm_text": psalm_text,
      "concluding_prayer": concluding_prayer,
      "luthers_morning_prayer": utils.OTHER_PRAYERS["luthers_morning_prayer"],
      "all_personal_prayers": all_personal_prayers,
  }
  print("Generated Morning HTML")
  return flask.render_template("morning_devotion.html", **template_data)
