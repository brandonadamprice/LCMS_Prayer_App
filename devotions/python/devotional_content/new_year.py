"""Functions for generating the New Year's devotion."""

import datetime
import flask
import utils


def generate_new_year_devotion(date_obj=None):
  """Generates HTML for the New Year's devotion."""
  eastern_timezone = utils.EASTERN_TZ
  now = date_obj or datetime.datetime.now(eastern_timezone)

  readings = ["Psalm 90", "Luke 2:21"]
  texts = utils.fetch_passages(readings)

  prev_date, next_date = utils.devotion_nav_dates(now)

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "prev_date": prev_date,
      "next_date": next_date,
      "psalm_text": texts[0],
      "gospel_text": texts[1],
  }

  return flask.render_template("new_year_devotion.html", **template_data)
