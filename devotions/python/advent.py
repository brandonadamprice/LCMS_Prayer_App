"""Functions for generating the Advent devotion."""

import datetime
import json
import os
import string
import pytz
import utils

ADVENT_HTML_TEMPLATE_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "html", "advent_devotion.html"
)
ADVENT_JSON_PATH = os.path.join(utils.SCRIPT_DIR, "..", "data", "advent.json")


def load_advent_devotions():
  with open(ADVENT_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def generate_advent_devotion():
  """Generates HTML for the Advent devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  day_of_month = now.day

  advent_devotions = load_advent_devotions()

  devotion_data = advent_devotions[day_of_month - 1]

  scripture_verses = devotion_data["scripture_verses"]
  reading_texts = utils.fetch_passages([scripture_verses])
  reading_text = reading_texts[0]

  reading_html = f"<p>{reading_text}</p>"

  meditation_html = f'<p>{devotion_data["brief_devotional"]}</p>'
  daily_prayer_html = f'<p>{devotion_data["short_prayer"]}</p>'

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "devotion_title": devotion_data["devotional_title"],
      "lords_prayer_html": utils.LORDS_PRAYER_HTML,
      "reading_ref": scripture_verses,
      "reading_html": reading_html,
      "meditation_html": meditation_html,
      "daily_prayer_html": daily_prayer_html,
  }

  with open(ADVENT_HTML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
    template = string.Template(f.read())

  html = template.substitute(template_data)
  print("Generated Advent HTML")
  return html
