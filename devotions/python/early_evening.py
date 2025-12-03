"""Functions for generating the early evening devotion."""

import datetime
import random
import flask
import pytz
import utils

EARLY_EVENING_READINGS = [
    "Luke 24:28-31",
    "Exodus 16:11-21,31",
    "Isaiah 25:6-9",
    "Matthew 14:15-21",
    "Matthew 27:57-60",
    "Luke 14:15-24",
    "John 6:25-35",
    "John 10:7-18",
    "Ephesians 6:10-18",
]


def generate_early_evening_devotion():
  """Generates HTML for the early evening devotion for the current date."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  template_data = utils.get_devotion_data(now)

  # We only need catechism and date from get_devotion_data
  # Reading and Psalm are specific to this office
  del template_data["psalm_ref"]
  del template_data["psalm_text"]
  del template_data["ot_reading_ref"]
  del template_data["ot_text"]
  del template_data["nt_reading_ref"]
  del template_data["nt_text"]
  del template_data["prayer_topic"]
  del template_data["weekly_prayer_html"]

  reading_ref = random.choice(EARLY_EVENING_READINGS)
  psalm_num = random.randint(1, 150)
  psalm_ref = f"Psalm {psalm_num}"

  reading_text, psalm_text = utils.fetch_passages([reading_ref, psalm_ref])
  template_data["reading_ref"] = reading_ref
  template_data["reading_text"] = reading_text
  template_data["psalm_ref"] = psalm_ref
  template_data["psalm_text"] = psalm_text

  print("Generated Early Evening HTML")
  return flask.render_template("early_evening_devotion.html", **template_data)
