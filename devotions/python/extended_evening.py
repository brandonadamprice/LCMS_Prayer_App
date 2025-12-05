"""Functions for generating the evening devotion."""

import datetime
import random
import flask
import pytz
import utils


def generate_extended_evening_devotion():
  """Generates HTML for the evening devotion for the current date.

  This function fetches lectionary readings, a psalm, and a catechism section
  based on the current date, combines them with a weekly prayer topic, and
  renders an HTML page.

  Returns:
      The generated HTML as a string.
  """
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  template_data = utils.get_devotion_data(now)
  template_data["concluding_prayer"] = random.choice(
      utils.OTHER_PRAYERS["close_of_day_prayers"]
  )
  template_data["luthers_evening_prayer"] = utils.OTHER_PRAYERS[
      "luthers_evening_prayer"
  ]

  print("Generated Evening HTML")
  return flask.render_template(
      "extended_evening_devotion.html", **template_data
  )
