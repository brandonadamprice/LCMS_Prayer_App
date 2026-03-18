"""Functions for generating the New Year's devotion."""

import datetime
import flask
import pytz
import utils


def generate_new_year_devotion(date_obj=None):
  """Generates HTML for the New Year's devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = date_obj or datetime.datetime.now(eastern_timezone)

  readings = ["Psalm 90", "Luke 2:21"]
  texts = utils.fetch_passages(readings)

  today_date = datetime.datetime.now(eastern_timezone).date()
  prev_date = (now.date() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
  next_day = now.date() + datetime.timedelta(days=1)
  next_date = next_day.strftime("%Y-%m-%d") if next_day <= today_date else None

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "prev_date": prev_date,
      "next_date": next_date,
      "psalm_text": texts[0],
      "gospel_text": texts[1],
  }

  print("Generated New Year's Devotion HTML")
  return flask.render_template("new_year_devotion.html", **template_data)
