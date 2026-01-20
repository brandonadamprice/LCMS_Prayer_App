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


def generate_advent_devotion(date_obj=None):
  """Generates HTML for the Advent devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = date_obj or datetime.datetime.now(eastern_timezone)
  day_of_month = now.day

  advent_devotions = load_advent_devotions()

  devotion_data = advent_devotions[day_of_month - 1]

  scripture_verses = devotion_data["scripture_verses"]
  reading_texts = utils.fetch_passages([scripture_verses])
  reading_text = reading_texts[0]

  # Advent candle lighting is based on the four Sundays preceding Christmas.
  # Candle 1 is lit on Advent 1, 2 on Advent 2, etc.
  year = now.year
  advent4_sunday = datetime.date(year, 12, 24)
  advent4_sunday -= datetime.timedelta(days=(advent4_sunday.weekday() + 1) % 7)
  advent3_sunday = advent4_sunday - datetime.timedelta(days=7)
  advent2_sunday = advent4_sunday - datetime.timedelta(days=14)
  advent1_sunday = advent4_sunday - datetime.timedelta(days=21)

  today = now.date()
  candle_1_lit = today >= advent1_sunday
  candle_2_lit = today >= advent2_sunday
  candle_3_lit = today >= advent3_sunday  # Pink candle
  candle_4_lit = today >= advent4_sunday
  candle_5_lit = today == datetime.date(year, 12, 25)  # Christ candle

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
