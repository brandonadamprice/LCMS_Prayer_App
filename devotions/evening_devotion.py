"""Generates and serves a daily evening devotion page.

This script fetches lectionary readings, a psalm, and a catechism section
based on the current date and the liturgical year. It then combines these
with a weekly prayer topic into an HTML page, which is served locally.
"""

import csv
import datetime
import json
import os
import random
import re
import pytz
from string import Template

import flask
import requests
import secrets_fetcher as secrets

app = flask.Flask(__name__)


# ==========================================
# CONFIGURATION
# ==========================================

# Get the directory where the script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Data file paths
LECTIONARY_CSV_PATH = os.path.join(SCRIPT_DIR, "daily_lectionary.csv")
CATECHISM_JSON_PATH = os.path.join(SCRIPT_DIR, "catechism.json")
EVENING_HTML_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "evening_devotion.html")
MORNING_HTML_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "morning_devotion.html")
WEEKLY_PRAYERS_JSON_PATH = os.path.join(SCRIPT_DIR, "weekly_prayers.json")
INDEX_HTML_PATH = os.path.join(SCRIPT_DIR, "index.html")


def load_weekly_prayers():
  with open(WEEKLY_PRAYERS_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def load_catechism():
  with open(CATECHISM_JSON_PATH, "r", encoding="utf-8") as f:
    catechism_data = json.load(f)
  for entry in catechism_data:
    if "<br><br><strong>OR:</strong><br><br>" in entry["prayer"]:
      prayers = entry["prayer"].split("<br><br><strong>OR:</strong><br><br>")
      entry["prayer1"] = prayers[0]
      entry["prayer2"] = prayers[1]
    else:
      entry["prayer1"] = entry["prayer"]
      entry["prayer2"] = None
    del entry["prayer"]
  return catechism_data


CATECHISM_SECTIONS = load_catechism()
WEEKLY_PRAYERS = load_weekly_prayers()
MORNING_READINGS = ["Colossians 3:1-4", "Exodus 15:1-11", "Isaiah 12:1-6", "Matthew 20:1-16", "Mark 13:32-36", "Luke 24:1-9", "John 21:4-14", "Ephesians 4:17-24", "Romans 6:1-4"]

# ==========================================
# LOGIC CLASS: CHURCH YEAR
# ==========================================


class ChurchYear:
  """Calculates and provides key dates for the Western Christian liturgical year.

  This class is used to determine dates such as Easter, Ash Wednesday,
  Pentecost, and Holy Trinity Sunday for a given year, which are essential
  for looking up lectionary readings.
  """

  def __init__(self, year):
    self.year = year
    self.easter_date = self.calculate_easter(year)
    self.ash_wednesday = self.easter_date - datetime.timedelta(days=46)
    self.pentecost = self.easter_date + datetime.timedelta(days=49)
    self.holy_trinity = self.pentecost + datetime.timedelta(days=7)

  def calculate_easter(self, year):
    """Calculates the date of Western Easter for a given year."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(year, month, day)

  def get_liturgical_key(self, current_date):
    """Determines the correct CSV key for the current date.

    Prioritizes the Movable Season (Ash Wed -> Trinity Sunday). If not in that
    season, returns the Fixed Date (e.g., "01 Jan").
    """
    # Convert to date object if it's datetime
    if isinstance(current_date, datetime.datetime):
      d = current_date.date()
    else:
      d = current_date

    # Check if we are in the Movable Season
    if self.ash_wednesday <= d <= self.holy_trinity:

      # CASE 1: Ash Wednesday to Holy Saturday
      if d < self.easter_date:
        days_since_ash = (d - self.ash_wednesday).days
        if days_since_ash == 0:
          return "Ash Wednesday"
        if days_since_ash == 1:
          return "Ash Thursday"
        if days_since_ash == 2:
          return "Ash Friday"
        if days_since_ash == 3:
          return "Ash Saturday"

        # Lent Weeks
        days_into_lent = days_since_ash - 4
        week_num = (days_into_lent // 7) + 1
        day_names = [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]
        weekday = day_names[days_into_lent % 7]

        # Special names for Holy Week (Lent 6)
        if week_num == 6:
          if weekday == "Sunday":
            return "Palm Sunday"
          if weekday == "Monday":
            return "Holy Week Monday"
          if weekday == "Tuesday":
            return "Holy Week Tuesday"
          if weekday == "Wednesday":
            return "Holy Week Wednesday"
          if weekday == "Thursday":
            return "Maundy Thursday"
          if weekday == "Friday":
            return "Good Friday"
          if weekday == "Saturday":
            return "Holy Saturday"

        return f"Lent {week_num} {weekday}"

      # CASE 2: Easter Season
      days_since_easter = (d - self.easter_date).days
      week_num = (days_since_easter // 7) + 1
      day_names = [
          "Sunday",
          "Monday",
          "Tuesday",
          "Wednesday",
          "Thursday",
          "Friday",
          "Saturday",
      ]
      weekday = day_names[days_since_easter % 7]

      if days_since_easter == 0:
        return "Easter Sunday"
      if days_since_easter == 39:
        return "Ascension Day"  # 40th day is Ascension (Thurs)
      if days_since_easter == 49:
        return "Pentecost Sunday"
      if days_since_easter >= 50 and days_since_easter < 56:
        # Pentecost Week (Often called Pentecost Monday etc)
        return f"Pentecost {weekday}"
      if days_since_easter == 56:
        return "Holy Trinity"

      # Standard Easter Weeks
      prefix = "Easter" if week_num == 1 else f"Easter {week_num}"
      return f"{prefix} {weekday}"

    # CASE 3: Fixed Date (Ordinary Time / Epiphany / Advent)
    return current_date.strftime("%d %b")


# ==========================================
# MAIN FUNCTIONS
# ==========================================


def load_lectionary(filepath):
  """Loads the CSV into a dictionary."""
  lectionary = {}
  if not os.path.exists(filepath):
    print(
        "CSV file not found. Please ensure lectionary.csv is in the same"
        " folder."
    )
    return {}

  with open(filepath, mode="r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
      lectionary[row["Key"]] = {
          "OT": row["OT"],
          "NT": row["NT"],
      }
  return lectionary


def fetch_passages(references):
  """Fetches multiple passages from api.esv.org in one request."""
  passage_results = {}
  valid_refs_set = set()
  for ref in references:
    if ref and ref != "Daily Lectionary Not Found":
      valid_refs_set.add(ref)
      passage_results[ref] = "<i>Reading not available.</i>"
    else:
      passage_results[ref] = "<i>Reading not available.</i>"

  valid_refs_list = sorted(
      list(valid_refs_set)
  )  # sorted to make query deterministic for caching/debugging

  if not valid_refs_list:
    return [passage_results[ref] for ref in references]

  api_key = secrets.get_esv_api_key()
  if not api_key:
    for ref in valid_refs_list:
      passage_results[ref] = (
          "<i>ESV_API_KEY environment variable not set. Cannot fetch text.</i>"
      )
    return [passage_results[ref] for ref in references]

  query = ";".join(valid_refs_list)
  params = {
      "q": query,
      "include-headings": "false",
      "include-footnotes": "false",
      "include-verse-numbers": "true",
      "include-passage-references": "false",
      "include-chapter-numbers": "false",
  }
  headers = {"Authorization": f"Token {api_key}"}

  try:
    response = requests.get(
        "https://api.esv.org/v3/passage/text/",
        params=params,
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("passages") and len(data["passages"]) == len(valid_refs_list):
      for i, ref in enumerate(valid_refs_list):
        text_block = data["passages"][i].strip()
        text_block = re.sub(r"\[(\d+)\]", r"<sup>\1</sup>", text_block)
        passage_results[ref] = text_block
    else:
      # If passages are missing or count mismatch, mark all as not found from API
      for ref in valid_refs_list:
        passage_results[ref] = f"<i>(Text not found for {ref})</i>"

    return [passage_results[ref] for ref in references]

  except requests.exceptions.RequestException as e:
    print(f"Error fetching from ESV API: {e}")
    error_msg = "<i>(Could not connect to ESV API)</i>"
    for ref in valid_refs_list:
      passage_results[ref] = error_msg
    return [passage_results[ref] for ref in references]
  except Exception as e:
    print(f"Error processing ESV API response: {e}")
    error_msg = "<i>(Error processing ESV API response)</i>"
    for ref in valid_refs_list:
      passage_results[ref] = error_msg
    return [passage_results[ref] for ref in references]


def get_devotion_data(now):
  """Fetches lectionary readings, a psalm, and a catechism section
  based on the current date, combines them with a weekly prayer topic, and
  returns a dictionary of data for rendering.
  """
  # 1. Setup Date & Church Year
  # Debugging: Uncomment to test a specific date
  # now = datetime.datetime(2025, 2, 26) # Ash Wednesday 2025 example

  cy = ChurchYear(now.year)

  # 2. Determine Key
  key = cy.get_liturgical_key(now)
  print(f"Generating devotion for: {now.strftime('%Y-%m-%d')}")
  print(f"Liturgical Key: {key}")

  # 3. Load Data
  data = load_lectionary(LECTIONARY_CSV_PATH)
  readings = data.get(
      key,
      {"OT": "Reading not found", "NT": "Reading not found"},
  )

  if readings["OT"] == "Reading not found":
    print(f"Warning: Key '{key}' not found in CSV.")

  # 4. Psalm Ref & Fetch Texts
  print("Fetching texts...")
  day_of_year = now.timetuple().tm_yday
  psalm_num = (day_of_year - 1) % 150 + 1
  psalm_ref = f"Psalm {psalm_num}"

  refs_to_fetch = [readings["OT"], readings["NT"], psalm_ref]
  ot_text, nt_text, psalm_text = fetch_passages(refs_to_fetch)
  print("Texts Acquired")

  # 5. Catechism
  cat_idx = day_of_year % len(CATECHISM_SECTIONS)
  catechism = CATECHISM_SECTIONS[cat_idx]
  print("Populated Catechism Reading")

  # 6. Weekly Prayer
  weekday_idx = now.weekday()
  prayer_data = WEEKLY_PRAYERS.get(
      str(weekday_idx), {"topic": "General Intercessions", "prayer": ""}
  )
  prayer_topic = prayer_data["topic"]
  weekly_prayer_html = (
      f'<p>{prayer_data["prayer"]}</p>' if prayer_data["prayer"] else ""
  )
  print("Populated Weekly Prayer section")

  # 7. Generate HTML
  catechism_meaning_html = ""
  if catechism["meaning"]:
    catechism_meaning_html = (
        f'<p><strong>Meaning:</strong> {catechism["meaning"]}</p>'
    )

  catechism_prayer = catechism["prayer1"]
  if catechism["prayer2"]:
    catechism_prayer = random.choice(
        [catechism["prayer1"], catechism["prayer2"]]
    )
  
  return {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "key": key,
      "catechism_title": catechism["title"],
      "catechism_text": catechism["text"],
      "catechism_meaning_html": catechism_meaning_html,
      "catechism_prayer": catechism_prayer,
      "psalm_ref": psalm_ref,
      "psalm_text": psalm_text,
      "ot_reading_ref": readings["OT"],
      "ot_text": ot_text,
      "nt_reading_ref": readings["NT"],
      "nt_text": nt_text,
      "prayer_topic": prayer_topic,
      "weekly_prayer_html": weekly_prayer_html,
  }

def generate_evening_devotion():
  """Generates HTML for the evening devotion for the current date.

  This function fetches lectionary readings, a psalm, and a catechism section
  based on the current date, combines them with a weekly prayer topic, and
  renders an HTML page.

  Returns:
      The generated HTML as a string.
  """
  eastern_timezone = pytz.timezone('America/New_York')
  now = datetime.datetime.now(eastern_timezone)
  template_data = get_devotion_data(now)

  with open(EVENING_HTML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
    template = Template(f.read())

  html = template.substitute(template_data)
  print("Generated Evening HTML")
  return html

def generate_morning_devotion():
  """Generates HTML for the morning devotion for the current date."""
  eastern_timezone = pytz.timezone('America/New_York')
  now = datetime.datetime.now(eastern_timezone)
  template_data = get_devotion_data(now)

  del template_data["catechism_title"]
  del template_data["catechism_text"]
  del template_data["catechism_meaning_html"]
  del template_data["catechism_prayer"]
  del template_data["prayer_topic"]
  del template_data["weekly_prayer_html"]

  morning_reading_ref = random.choice(MORNING_READINGS)
  psalm_num = random.randint(1, 150)
  psalm_ref = f"Psalm {psalm_num}"

  reading_text, psalm_text = fetch_passages([morning_reading_ref, psalm_ref])
  template_data["reading_ref"] = morning_reading_ref
  template_data["reading_text"] = reading_text
  template_data["psalm_ref"] = psalm_ref
  template_data["psalm_text"] = psalm_text

  with open(MORNING_HTML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
    template = Template(f.read())

  html = template.substitute(template_data)
  print("Generated Morning HTML")
  return html


@app.route("/")
def index_route():
  """Returns the homepage HTML."""
  with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
    return f.read()


@app.route("/evening_devotion")
def evening_devotion_route():
  """Returns the generated devotion HTML."""
  return generate_evening_devotion()

@app.route("/morning_devotion")
def morning_devotion_route():
  """Returns the generated devotion HTML."""
  return generate_morning_devotion()


if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
