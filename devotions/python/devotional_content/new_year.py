"""Functions for generating the New Year's devotion."""

import datetime
import flask
import pytz
import utils


def generate_new_year_devotion():
  """Generates HTML for the New Year's devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)

  readings = ["Psalm 90", "Luke 2:21"]
  texts = utils.fetch_passages(readings)

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "psalm_text": texts[0],
      "gospel_text": texts[1],
  }

  print("Generated New Year's Devotion HTML")
  return flask.render_template("new_year_devotion.html", **template_data)
