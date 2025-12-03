"""Functions for generating the close of day devotion."""

import datetime
import random
import flask
import pytz
import utils

CLOSE_OF_DAY_READINGS = [
    "Matthew 11:28-30",
    "Micah 7:18-20",
    "Matthew 18:15-35",
    "Matthew 25:1-13",
    "Luke 11:1-13",
    "Luke 12:13-34",
    "Romans 8:31-39",
    "2 Corinthians 4:16-18",
    "Revelation 21:22-22:5",
]


def generate_close_of_day_devotion():
  """Generates HTML for the close of day devotion for the current date."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  template_data = utils.get_devotion_data(now)

  # We only need weekly prayer and date from get_devotion_data
  # Reading is specific to this office, no psalm or catechism
  del template_data["psalm_ref"]
  del template_data["psalm_text"]
  del template_data["ot_reading_ref"]
  del template_data["ot_text"]
  del template_data["nt_reading_ref"]
  del template_data["nt_text"]
  del template_data["catechism_title"]
  del template_data["catechism_text"]
  del template_data["catechism_meaning_html"]
  del template_data["catechism_prayer"]

  reading_ref = random.choice(CLOSE_OF_DAY_READINGS)
  reading_text = utils.fetch_passages([reading_ref])[0]
  template_data["reading_ref"] = reading_ref
  template_data["reading_text"] = reading_text

  print("Generated Close of Day HTML")
  return flask.render_template("close_of_day_devotion.html", **template_data)
