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
  psalm_num = random.randint(1, 150)
  psalm_ref = f"Psalm {psalm_num}"
  reading_text, psalm_text = utils.fetch_passages([reading_ref, psalm_ref])
  concluding_prayer = utils.OTHER_PRAYERS["evening_prayers"]
  all_personal_prayers = utils.get_all_personal_prayers_for_user()

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "key": key,
      "reading_ref": reading_ref,
      "reading_options": utils.OFFICE_READINGS["evening_readings"],
      "reading_text": reading_text,
      "psalm_ref": psalm_ref,
      "psalm_text": psalm_text,
      "concluding_prayer": concluding_prayer,
      "all_personal_prayers": all_personal_prayers,
  }
  template_data.update(catechism_data)

  print("Generated Evening HTML")
  return flask.render_template("evening_devotion.html", **template_data)
