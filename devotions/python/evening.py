"""Functions for generating the evening devotion."""

import datetime
import os
import string
import pytz
from . import utils


EVENING_HTML_TEMPLATE_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "html", "evening_devotion.html"
)


def generate_evening_devotion():
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

  with open(EVENING_HTML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
    template = string.Template(f.read())

  html = template.substitute(template_data)
  print("Generated Evening HTML")
  return html
