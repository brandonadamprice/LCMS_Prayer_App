"""Shared utility functions and data for devotions."""

import csv
import datetime
import json
import os
import random
import re
import requests
import secrets_fetcher as secrets

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
LECTIONARY_CSV_PATH = os.path.join(DATA_DIR, "daily_lectionary.csv")
CATECHISM_JSON_PATH = os.path.join(DATA_DIR, "catechism.json")
WEEKLY_PRAYERS_JSON_PATH = os.path.join(DATA_DIR, "weekly_prayers.json")
INAPPROPRIATE_WORDS_CSV_PATH = os.path.join(DATA_DIR, "inappropriate_words.csv")


def load_inappropriate_words():
  """Loads inappropriate words from a CSV file into a set."""
  words = set()
  try:
    with open(INAPPROPRIATE_WORDS_CSV_PATH, "r", encoding="utf-8") as f:
      reader = csv.DictReader(f)
      for row in reader:
        if "word" in row and row["word"]:
          words.add(row["word"].strip().lower())
  except FileNotFoundError:
    print(f"Warning: {INAPPROPRIATE_WORDS_CSV_PATH} not found.")
  return words


INAPPROPRIATE_WORDS = load_inappropriate_words()


def is_inappropriate(text):
  """Checks if text contains inappropriate words, handling some obfuscation."""
  if not text:
    return False

  # Normalize: lowercase, leetspeak, symbols
  cleaned = text.lower()
  subs = {
      "@": "a",
      "4": "a",
      "8": "b",
      "(": "c",
      "[": "c",
      "{": "c",
      "<": "c",
      "3": "e",
      "6": "g",
      "9": "g",
      "!": "i",
      "1": "i",
      "|": "i",
      "0": "o",
      "$": "s",
      "5": "s",
      "+": "t",
      "7": "t",
      "2": "z",
  }
  for key, value in subs.items():
    cleaned = cleaned.replace(key, value)

  # Remove any character that is not a letter or space, then split
  cleaned = re.sub(r"[^a-z\s]", "", cleaned)
  words = set(cleaned.split())
  # Return True if any word in the text is in our inappropriate list
  return not INAPPROPRIATE_WORDS.isdisjoint(words)


def contains_phone_number(text):
  """Checks if a string contains a common phone number pattern.

  This pattern looks for 7-10 digits, optionally separated by hyphens, spaces,
  or enclosed in parentheses. It also accounts for optional country codes (e.g.,
  +1).

  Args:
    text: The text to check for phone numbers.

  Returns:
    True if a phone number is found, False otherwise.
  """
  # This regex attempts to capture various phone number formats.
  # It's a simplified example and might need adjustment for specific regional
  # formats.
  phone_pattern = r"(\+\d{1,3}\s?)?(\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}"

  return bool(re.search(phone_pattern, text))


def load_weekly_prayers():
  """Loads weekly prayers from JSON file."""
  with open(WEEKLY_PRAYERS_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def load_catechism():
  """Loads catechism data from JSON file."""
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

LORDS_PRAYER_HTML = """<p class="subheader"><strong>The Lord's Prayer</strong></p>
<p><strong>
Our Father who art in heaven,<br>
hallowed be Thy name,<br>
Thy kingdom come,<br>
Thy will be done<br>
on earth as it is in heaven.<br>
Give us this day our daily bread;<br>
and forgive us our trespasses<br>
as we forgive those who trespass against us;<br>
and lead us not into temptation,<br>
but deliver us from evil.<br>
For Thine is the kingdom<br>
and the power and the glory<br>
forever and ever. Amen.</strong>
<span class="versicle-ref">Matthew 6:9-13</span></p>"""

NUNC_DIMITTIS_HTML = """<p class="subheader"><strong>Nunc Dimittis</strong></p>
<p><strong>
Lord, now You let Your servant go in peace;<br>
    Your word has been fulfilled.<br>
My own eyes have seen the salvation<br>
    which You have prepared in the sight of every people:<br>
a light to reveal You to the nations<br>
    and the glory of Your people Israel.<br>
Glory be to the Father and to the Son and to the Holy Spirit;<br>
as it was in the beginning, is now, and will be forever. Amen.<br></strong>
<span class="versicle-ref">Luke 2:29-32</span></p>"""

APOSTLES_CREED_HTML = """<p class="subheader"><strong>The Apostles' Creed</strong></p>
<p><strong>
I believe in God, the Father Almighty, maker of heaven and earth.<br><br>
And in Jesus Christ, His only Son, our Lord, who was conceived by the Holy Spirit, born of the virgin Mary, suffered under Pontius Pilate, was crucified, died and was buried. He descended into hell. The third day He rose again from the dead. He ascended into heaven and sits at the right hand of God the Father Almighty. From thence He will come to judge the living and the dead.<br><br>
I believe in the Holy Spirit, the holy Christian Church, the communion of saints, the forgiveness of sins, the resurrection of the body, and the life everlasting. Amen.</strong></p>"""


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
      "apostles_creed_html": APOSTLES_CREED_HTML,
      "nt_text": nt_text,
      "prayer_topic": prayer_topic,
      "weekly_prayer_html": weekly_prayer_html,
      "lords_prayer_html": LORDS_PRAYER_HTML,
      "nunc_dimittis_html": NUNC_DIMITTIS_HTML,
  }


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
        text_block = re.sub(r"\[(\d+)\]", r"<br><sup>\1</sup>", text_block)
        if text_block.startswith("<br>"):
          text_block = text_block[4:]
        passage_results[ref] = text_block
    else:
      # If passages are missing or count mismatch, mark all as not found
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
