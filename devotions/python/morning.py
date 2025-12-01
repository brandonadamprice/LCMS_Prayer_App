"""Functions for generating the morning devotion."""

import datetime
import os
import random
import string
import pytz
from . import utils

MORNING_HTML_TEMPLATE_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "html", "morning_devotion.html"
)
MORNING_READINGS = [
    "Colossians 3:1-4",
    "Exodus 15:1-11",
    "Isaiah 12:1-6",
    "Matthew 20:1-16",
    "Mark 13:32-36",
    "Luke 24:1-9",
    "John 21:4-14",
    "Ephesians 4:17-24",
    "Romans 6:1-4",
]


def generate_morning_devotion():
  """Generates HTML for the morning devotion for the current date."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  template_data = utils.get_devotion_data(now)

  del template_data["catechism_title"]
  del template_data["catechism_text"]
  del template_data["catechism_meaning_html"]
  del template_data["catechism_prayer"]
  del template_data["prayer_topic"]
  del template_data["weekly_prayer_html"]

  morning_reading_ref = random.choice(MORNING_READINGS)
  psalm_num = random.randint(1, 150)
  psalm_ref = f"Psalm {psalm_num}"

  reading_text, psalm_text = utils.fetch_passages(
      [morning_reading_ref, psalm_ref]
  )
  template_data["reading_ref"] = morning_reading_ref
  template_data["reading_text"] = reading_text
  template_data["psalm_ref"] = psalm_ref
  template_data["psalm_text"] = psalm_text

  with open(MORNING_HTML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
    template = string.Template(f.read())

  html = template.substitute(template_data)
  print("Generated Morning HTML")
  return html
