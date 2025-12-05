"""Functions for generating the Night Watch devotion."""

import datetime
import random
import flask
import pytz
import utils


def generate_night_watch_devotion():
  """Generates HTML for the Night Watch devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  psalm_ref = random.choice(utils.OFFICE_READINGS["night_watch_psalms"])
  reading_ref = random.choice(utils.OFFICE_READINGS["night_watch_readings"])
  psalm_text, reading_text = utils.fetch_passages([psalm_ref, reading_ref])
  protection_prayer = utils.OTHER_PRAYERS["night_watch_protection_prayers"]
  concluding_prayer = utils.OTHER_PRAYERS["night_watch_concluding_prayers"]

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "psalm_ref": psalm_ref,
      "psalm_text": psalm_text,
      "reading_ref": reading_ref,
      "reading_text": reading_text,
      "protection_prayer": protection_prayer,
      "concluding_prayer": concluding_prayer,
  }
  print("Generated Night Watch HTML")
  return flask.render_template("night_watch_devotion.html", **template_data)
