"""Functions for generating the Advent devotion."""

import datetime
import json
import os
import flask
import pytz
import utils

ADVENT_JSON_PATH = os.path.join(utils.SCRIPT_DIR, "..", "data", "advent.json")


def load_advent_devotions():
  """Loads advent devotions from JSON file."""
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

  # This logic is based on 2025
  candle_1_lit = day_of_month >= 1
  candle_2_lit = day_of_month >= 7
  candle_3_lit = day_of_month >= 14
  candle_4_lit = day_of_month >= 21
  candle_5_lit = day_of_month == 25

  reading_html = f"<p>{reading_text}</p>"

  meditation_html = f'<p>{devotion_data["brief_devotional"]}</p>'
  daily_prayer_html = f'<p>{devotion_data["short_prayer"]}</p>'

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "devotion_title": devotion_data["devotional_title"],
      "reading_ref": scripture_verses,
      "reading_html": reading_html,
      "meditation_html": meditation_html,
      "daily_prayer_html": daily_prayer_html,
      "candle_1_lit": candle_1_lit,
      "candle_2_lit": candle_2_lit,
      "candle_3_lit": candle_3_lit,
      "candle_4_lit": candle_4_lit,
      "candle_5_lit": candle_5_lit,
  }

  print("Generated Advent HTML")
  return flask.render_template("advent_devotion.html", **template_data)
