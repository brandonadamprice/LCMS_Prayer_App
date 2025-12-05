"""Functions for generating the midday devotion."""

import datetime
import random
import flask
import pytz
import utils


def generate_midday_devotion():
  """Generates HTML for the midday devotion for the current date."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  cy = utils.ChurchYear(now.year)
  key = cy.get_liturgical_key(now)

  reading_ref = random.choice(utils.OFFICE_READINGS["noon_readings"])
  psalm_num = random.randint(1, 150)
  psalm_ref = f"Psalm {psalm_num}"

  reading_text, psalm_text = utils.fetch_passages([reading_ref, psalm_ref])
  concluding_prayer = random.choice(utils.OFFICE_READINGS["noon_prayers"])

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "key": key,
      "reading_ref": reading_ref,
      "reading_text": reading_text,
      "psalm_ref": psalm_ref,
      "psalm_text": psalm_text,
      "concluding_prayer": concluding_prayer,
  }
  print("Generated Midday HTML")
  return flask.render_template("midday_devotion.html", **template_data)
