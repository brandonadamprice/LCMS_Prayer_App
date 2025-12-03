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
  reading_text = utils.fetch_passages([reading_ref])[0]

  weekly_prayer_data = utils.get_weekly_prayer_for_day(now)

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "key": key,
      "reading_ref": reading_ref,
      "reading_text": reading_text,
  }
  template_data.update(weekly_prayer_data)
  print("Generated Close of Day HTML")
  return flask.render_template("close_of_day_devotion.html", **template_data)
