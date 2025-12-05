"""Shared utility functions and data for devotions."""

import csv
import datetime
import functools
import json
import os
import random
import re
from google.cloud import firestore
import requests
import secrets_fetcher as secrets

# Flag to enable/disable Catechism section in devotions
# TODO(baprice): Enable catechism once we have permission from CPH to use it.
ENABLE_CATECHISM = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
LECTIONARY_JSON_PATH = os.path.join(DATA_DIR, "daily_lectionary.json")
CATECHISM_JSON_PATH = os.path.join(DATA_DIR, "catechism.json")
WEEKLY_PRAYERS_JSON_PATH = os.path.join(DATA_DIR, "weekly_prayers.json")
OFFICE_READINGS_JSON_PATH = os.path.join(DATA_DIR, "office_readings.json")
OTHER_PRAYERS_JSON_PATH = os.path.join(DATA_DIR, "other_prayers.json")
INAPPROPRIATE_WORDS_CSV_PATH = os.path.join(DATA_DIR, "inappropriate_words.csv")


def get_db_client():
  """Initializes and returns a Firestore client."""
  # In a GCP environment (Cloud Run, GAE), the client automatically
  # authenticates using the service account or application default credentials.
  # For local development, ensure you have authenticated via gcloud:
  # `gcloud auth application-default login`
  return firestore.Client(
      project="lcms-prayer-app", database="prayer-app-datastore"
  )


def load_office_readings():
  """Loads office readings from JSON file."""
  with open(OFFICE_READINGS_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


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
  return catechism_data


def load_other_prayers():
  """Loads other prayers from JSON file."""
  with open(OTHER_PRAYERS_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


CATECHISM_SECTIONS = load_catechism()
WEEKLY_PRAYERS = load_weekly_prayers()
OFFICE_READINGS = load_office_readings()
OTHER_PRAYERS = load_other_prayers()

def get_other_prayers():
  """Returns the OTHER_PRAYERS dictionary."""
  return OTHER_PRAYERS

def get_catechism_for_day(now: datetime.datetime) -> dict:
  """Returns the catechism section for a given day."""
  if not ENABLE_CATECHISM:
    return {"catechism_enabled": False}
  day_of_year = now.timetuple().tm_yday
  cat_idx = day_of_year % len(CATECHISM_SECTIONS)
  catechism = CATECHISM_SECTIONS[cat_idx]
  meaning_html = (
      f'<p><strong>Meaning:</strong> {catechism["meaning"]}</p>'
      if catechism["meaning"]
      else ""
  )
  prayer = random.choice(catechism["prayers"])
  return {
      "catechism_enabled": True,
      "catechism_title": catechism["title"],
      "catechism_text": catechism["text"],
      "catechism_meaning_html": meaning_html,
      "catechism_prayer": prayer,
  }


def get_weekly_prayer_for_day(now: datetime.datetime) -> dict:
  """Returns the weekly prayer topic and text for a given day."""
  weekday_idx = now.weekday()
  prayer_data = WEEKLY_PRAYERS.get(
      str(weekday_idx), {"topic": "General Intercessions", "prayer": ""}
  )
  return {
      "prayer_topic": prayer_data["topic"],
      "weekly_prayer_html": (
          f'<p>{prayer_data["prayer"]}</p>' if prayer_data["prayer"] else ""
      ),
  }


def generate_category_page_data(json_path: str) -> list[dict]:
  """Loads category data from JSON, selects a random verse, and fetches text."""
  with open(json_path, "r", encoding="utf-8") as f:
    categories = json.load(f)
  refs = [random.choice(cat["verses"]) for cat in categories]
  texts = fetch_passages(refs)
  category_data = []
  for i, cat in enumerate(categories):
    category_data.append({
        "title": cat["title"],
        "description": cat["description"],
        "verses": cat["verses"],
        "prayer": cat["prayer"],
        "initial_ref": refs[i],
        "initial_text": texts[i],
    })
  return category_data


class ChurchYear:
  """Calculates and provides key dates for the Western Christian liturgical year.

  This class is used to determine dates such as Easter, Ash Wednesday,
  Pentecost, and Holy Trinity Sunday for a given year, which are essential
  for looking up lectionary readings.
  """

  def __init__(self, year: int):
    self.year = year
    self.easter_date = self.calculate_easter(year)
    self.ash_wednesday = self.easter_date - datetime.timedelta(days=46)
    self.pentecost = self.easter_date + datetime.timedelta(days=49)
    self.holy_trinity = self.pentecost + datetime.timedelta(days=7)

  def calculate_easter(self, year: int) -> datetime.date:
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

  def get_liturgical_key(self, current_date: datetime.date) -> str:
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


def load_lectionary(filepath: str) -> dict:
  """Loads the lectionary data from a JSON file."""
  if not os.path.exists(filepath):
    print(f"JSON file not found: {filepath}")
    return {}
  with open(filepath, mode="r", encoding="utf-8") as f:
    return json.load(f)


def get_devotion_data(now: datetime.datetime) -> dict:
  """Fetches lectionary readings, a psalm, and a catechism section.

  Args:
    now: The current datetime.datetime object.

  Returns:
    A dictionary of data for rendering the devotion.

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
  data = load_lectionary(LECTIONARY_JSON_PATH)
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

  # 5. Catechism - USE HELPER
  catechism_data = get_catechism_for_day(now)
  print("Populated Catechism Reading")

  # 6. Weekly Prayer - USE HELPER
  weekly_prayer_data = get_weekly_prayer_for_day(now)
  print("Populated Weekly Prayer section")

  # 7. Combine data
  data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "key": key,
      "psalm_ref": psalm_ref,
      "psalm_text": psalm_text,
      "ot_reading_ref": readings["OT"],
      "ot_text": ot_text,
      "nt_reading_ref": readings["NT"],
      "nt_text": nt_text,
  }
  data.update(catechism_data)
  data.update(weekly_prayer_data)
  return data


def _preprocess_ref(ref: str) -> str:
  """Expands shorthand Bible references with semicolons and commas.

  Example: '1 Cor 7:17;23-24' becomes '1 Cor 7:17;1 Cor 7:23-24'.
  'Gen 27:30-45; 28:10-22' becomes 'Gen 27:30-45;Gen 28:10-22'.
  '2 John 1-13; 3 John 1-15' remains '2 John 1-13;3 John 1-15'.
  Handles verses only, or chapter:verses after semicolon.
  """
  splitting_delimiters = [";", ","]
  delim = ""
  for splitting_delimiter in splitting_delimiters:
    if splitting_delimiter in ref:
      delim = splitting_delimiter
      break
  if not delim:
    return ref

  parts = ref.split(delim)
  first_part = parts[0].strip()
  book_chapter_if_present = ""

  colon_idx = first_part.rfind(":")
  if colon_idx > -1:
    # multi-chapter book reference format, e.g. "Genesis 1:1"
    book_chapter_if_present = first_part[:colon_idx].strip()
    # regex to capture book name and chapter number
    book_match = re.match(r"(.*\D)\s*(\d+)$", book_chapter_if_present)
    if book_match:
      book = book_match.group(1).strip()
    else:
      book = ""
  else:
    # single-chapter book reference format, like "Jude 1-4" or "2 John 10"
    first_digit_match = re.search(r"\d", first_part)
    if first_digit_match:
      book = first_part[: first_digit_match.start()].strip()
    else:
      book = ""

  if not book:
    return ref

  processed_parts = [first_part]
  for part in parts[1:]:
    part = part.strip()
    if re.fullmatch(r"\d+(-\d+)?", part):  # verses only
      if book_chapter_if_present:
        processed_parts.append(f"{book_chapter_if_present}:{part}")
      else:  # single chapter book
        processed_parts.append(f"{book} {part}")
    elif re.fullmatch(r"\d+:\d+(-\d+)?", part):  # chapter:verses
      processed_parts.append(f"{book} {part}")
    else:  # Likely a full reference like '3 John 1-15', keep as is.
      processed_parts.append(part)
  return ";".join(processed_parts)


@functools.lru_cache(maxsize=512)
def _fetch_passages_cached(references: tuple[str, ...]) -> tuple[str, ...]:
  """Cached fetching of passages from api.esv.org."""
  passage_results = {}
  references_list = list(references)

  # original_ref -> list of preprocessed refs for ESV
  ref_map = {}
  esv_query_parts = []

  for ref in references_list:
    if ref and ref != "Daily Lectionary Not Found":
      preref = _preprocess_ref(ref)
      ref_map[ref] = preref.split(";")
      esv_query_parts.append(preref)
      passage_results[ref] = "<i>Reading not available.</i>"
    else:
      passage_results[ref] = "<i>Reading not available.</i>"

  if not esv_query_parts:
    return tuple(passage_results[ref] for ref in references_list)

  api_key = secrets.get_esv_api_key()
  if not api_key:
    for ref in ref_map:
      passage_results[ref] = (
          "<i>ESV_API_KEY environment variable not set. Cannot fetch text.</i>"
      )
    return tuple(passage_results[ref] for ref in references_list)

  query = ";".join(esv_query_parts)
  params = {
      "q": query,
      "include-headings": "false",
      "include-footnotes": "false",
      "include-verse-numbers": "true",
      "include-passage-references": "false",
      "include-chapter-numbers": "false",
      "include-copyright": "false",
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

    if data.get("passages"):
      passage_idx = 0
      for ref in references_list:
        if ref in ref_map:
          num_passages = len(ref_map[ref])
          if passage_idx + num_passages <= len(data["passages"]):
            passages_list = data["passages"][
                passage_idx : passage_idx + num_passages
            ]
            if passages_list:
              if len(passages_list) > 1:
                processed_passages = [
                    p.strip().removesuffix(" (ESV)") for p in passages_list[:-1]
                ]
                processed_passages.append(passages_list[-1].strip())
                text_block = " ".join(processed_passages)
              else:
                text_block = passages_list[0].strip()
            else:
              text_block = ""
            text_block = re.sub(r"\[(\d+)\]", r"<br><sup>\1</sup>", text_block)
            if text_block.startswith("<br>"):
              text_block = text_block[4:]
            passage_results[ref] = text_block
            passage_idx += num_passages
          else:
            passage_results[ref] = f"<i>(Text not found for {ref})</i>"
        # If ref not in ref_map, it's already "Reading not available"
    else:
      for ref in ref_map:
        passage_results[ref] = f"<i>(Text not found for {ref})</i>"

    return tuple(passage_results[ref] for ref in references_list)

  except requests.exceptions.RequestException as e:
    print(f"Error fetching from ESV API: {e}")
    error_msg = "<i>(Could not connect to ESV API)</i>"
    for ref in ref_map:
      passage_results[ref] = error_msg
    return tuple(passage_results[ref] for ref in references_list)
  except Exception as e:
    print(f"Error processing ESV API response: {e}")
    error_msg = "<i>(Error processing ESV API response)</i>"
    for ref in ref_map:
      passage_results[ref] = error_msg
    return tuple(passage_results[ref] for ref in references_list)


def fetch_passages(references: list[str]) -> list[str]:
  """Fetches multiple passages from api.esv.org in one request."""
  return list(_fetch_passages_cached(tuple(references)))
