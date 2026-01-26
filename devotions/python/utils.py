"""Shared utility functions and data for devotions."""

import csv
import datetime
import functools
import json
import os
import re
from typing import Optional

import cryptography.fernet
import flask_login
from google.cloud import firestore
import liturgy
import pytz
import secrets_fetcher as secrets
from services import scripture

# Flag to enable/disable Catechism section in devotions
ENABLE_CATECHISM = True

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")
LECTIONARY_JSON_PATH = os.path.join(DATA_DIR, "daily_lectionary.json")
CATECHISM_JSON_PATH = os.path.join(DATA_DIR, "catechism.json")
WEEKLY_PRAYERS_JSON_PATH = os.path.join(DATA_DIR, "weekly_prayers.json")
OFFICE_READINGS_JSON_PATH = os.path.join(DATA_DIR, "office_readings.json")
OTHER_PRAYERS_JSON_PATH = os.path.join(DATA_DIR, "other_prayers.json")
INAPPROPRIATE_WORDS_CSV_PATH = os.path.join(DATA_DIR, "inappropriate_words.csv")
MID_WEEK_READINGS_JSON_PATH = os.path.join(DATA_DIR, "mid_week_readings.json")
LITURGICAL_YEAR_JSON_PATH = os.path.join(DATA_DIR, "liturgical_year.json")
BIBLE_IN_A_YEAR_JSON_PATH = os.path.join(DATA_DIR, "bible_in_a_year.json")


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


def fetch_passages(
    references: list[str],
    include_verse_numbers: bool = True,
    include_copyright: bool = True,
) -> list[str]:
  """Fetches multiple passages from api.esv.org in one request."""
  return scripture.fetch_passages(
      references, include_verse_numbers, include_copyright
  )


def inject_references_in_text(text):
  """Finds scripture references in text and replaces them with tooltip spans."""
  if not text:
    return text

  text = re.sub(r"\*\*([^\*]+?)\*\*", r"<strong>\1</strong>", text)
  text = re.sub(r"\*([^\*]+?)\*", r"<strong>\1</strong>", text)
  text = re.sub(r"\bOT\b", "Old Testament", text)
  # Detects a valid Bible reference in the text. Don't ask how this works.
  pattern = r"\b((?:[1-3]\s)?[A-Za-z]+(?:(?:\s(?:of\s)?)?[A-Za-z]+){0,3}\s+\d+(?::\d+(?:(?:-)\d+)*)?(?:ff|f)?)\b"

  matches = list(set(re.findall(pattern, text)))
  if not matches:
    return text

  # Clean refs for API
  clean_refs = []
  for m in matches:
    clean = m.replace("–", "-").replace("ff", "").replace("f", "").strip()
    clean_refs.append(clean)

  try:
    texts = fetch_passages(
        clean_refs, include_verse_numbers=False, include_copyright=False
    )
    ref_map = dict(zip(matches, texts))

    def replace_match(m):
      ref_str = m.group(1)
      if ref_str not in ref_map:
        return ref_str

      scripture_text = ref_map[ref_str]
      if (
          "Reading not available" in scripture_text
          or "ESV API" in scripture_text
      ):
        return ref_str

      escaped_text = scripture_text.replace('"', "&quot;")
      return (
          f'<span class="scripture-tooltip" data-text="{ref_str} &mdash;'
          f' {escaped_text}">{ref_str}</span>'
      )

    # Use re.sub with a callback to safely replace in one pass
    # This avoids nested replacements if one reference is a substring of another
    text = re.sub(pattern, replace_match, text)

  except Exception as e:
    print(f"Error injecting references: {e}")

  return text


def process_node(node):
  """Recursively processes nodes to inject tooltips into string values."""
  if isinstance(node, dict):
    return {k: process_node(v) for k, v in node.items()}
  elif isinstance(node, list):
    return [process_node(i) for i in node]
  elif isinstance(node, str):
    return inject_references_in_text(node)
  else:
    return node


def load_weekly_prayers():
  """Loads weekly prayers from JSON file."""
  with open(WEEKLY_PRAYERS_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def load_catechism():
  """Loads catechism data from JSON file."""
  with open(CATECHISM_JSON_PATH, "r", encoding="utf-8") as f:
    catechism_data = json.load(f)
  return process_node(catechism_data)


def load_other_prayers():
  """Loads other prayers from JSON file."""
  with open(OTHER_PRAYERS_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def load_mid_week_readings():
  """Loads mid week readings from JSON file."""
  with open(MID_WEEK_READINGS_JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)
    for item in data:
      if "church_season/day" in item:
        item["church_season_day"] = item.pop("church_season/day")
    return {"extended_mid_week_devotions": data}


def load_bible_in_a_year_data():
  """Loads Bible in a Year data from JSON file."""
  with open(BIBLE_IN_A_YEAR_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


CATECHISM_SECTIONS = load_catechism()
WEEKLY_PRAYERS = load_weekly_prayers()
OFFICE_READINGS = load_office_readings()
OTHER_PRAYERS = load_other_prayers()
MID_WEEK_READINGS = load_mid_week_readings()


def get_other_prayers():
  """Returns the OTHER_PRAYERS dictionary."""
  return OTHER_PRAYERS


@functools.lru_cache()
def get_fernet():
  """Initializes and returns a Fernet instance with the key."""
  key = secrets.get_fernet_key()
  return cryptography.fernet.Fernet(key.encode())


def encrypt_text(text: str) -> str:
  """Encrypts text using Fernet."""
  f = get_fernet()
  return f.encrypt(text.encode()).decode()


def decrypt_text(token: str) -> str:
  """Decrypts a Fernet token."""
  try:
    f = get_fernet()
    return f.decrypt(token.encode()).decode()
  except Exception as e:
    print(f"Error decrypting token: {e}")
    return "[Error decrypting prayer]"


def get_deterministic_choice(options: list, date_obj: datetime.datetime) -> any:
  """Selects an item from options deterministically based on the date."""
  if not options:
    return None
  # Use day of year for deterministic rotation
  day_of_year = date_obj.timetuple().tm_yday
  return options[(day_of_year - 1) % len(options)]


def get_catechism_for_day(
    now: datetime.datetime, rotation: str = "daily"
) -> dict:
  """Returns the catechism section for a given day or week."""
  if not ENABLE_CATECHISM:
    return {"catechism_enabled": False}

  if rotation == "weekly":
    item_of_year = now.isocalendar()[1]  # week number
  else:  # daily
    item_of_year = now.timetuple().tm_yday  # day of year

  cat_idx = (item_of_year - 1) % len(CATECHISM_SECTIONS)
  catechism = CATECHISM_SECTIONS[cat_idx]
  prayer = get_deterministic_choice(catechism["prayers"], now)
  return {
      "catechism_enabled": True,
      "catechism_title": catechism["title"],
      "catechism_text": catechism["text"],
      "questions_and_answers": catechism["questions_and_answers"],
      "catechism_prayer": prayer,
  }


def get_weekly_prayer_for_day(now: datetime.datetime, user_id=None) -> dict:
  """Returns the weekly prayer topic and text for a given day."""
  weekday_idx = now.weekday()
  prayer_data = WEEKLY_PRAYERS.get(
      str(weekday_idx), {"topic": "General Intercessions", "prayer": ""}
  )
  topic = prayer_data["topic"]
  personal_prayers_list = []

  target_id = user_id
  if target_id is None and flask_login.current_user.is_authenticated:
    target_id = flask_login.current_user.id

  if target_id:
    raw_prayers = fetch_personal_prayers(target_id)
    for prayer in raw_prayers:
      if prayer.get("category") == topic:
        prayer["text"] = decrypt_text(prayer["text"])
        if prayer.get("for_whom"):
          prayer["for_whom"] = decrypt_text(prayer["for_whom"])
        personal_prayers_list.append(prayer)

  return {
      "prayer_topic": topic,
      "weekly_prayer_html": (
          f'<p>{prayer_data["prayer"]}</p>' if prayer_data["prayer"] else ""
      ),
      "personal_prayers_list": personal_prayers_list,
  }


def generate_category_page_data(json_path: str) -> list[dict]:
  """Loads category data from JSON, selects a deterministic verse, and fetches text."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)

  with open(json_path, "r", encoding="utf-8") as f:
    categories = json.load(f)
  refs = [get_deterministic_choice(cat["verses"], now) for cat in categories]
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


# Re-export ChurchYear for backward compatibility
# TODO(baprice): Remove this once all references are updated.
ChurchYear = liturgy.ChurchYear


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

  cy = liturgy.ChurchYear(now.year)

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
  catechism_data = get_catechism_for_day(now, rotation="daily")
  print("Populated Catechism Reading")

  # 6. Weekly Prayer - USE HELPER
  weekly_prayer_data = get_weekly_prayer_for_day(now)
  print("Populated Weekly Prayer section")

  # 7. Combine data
  data = {
      "is_trinity_sunday": now.date() == cy.holy_trinity,
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


def fetch_personal_prayers(user_id: str) -> list[dict]:
  """Fetches personal prayers for a user from their subcollection."""
  db = get_db_client()
  collection_ref = (
      db.collection("users").document(user_id).collection("personal-prayers")
  )

  prayers = []
  try:
    new_docs = collection_ref.stream()
    for doc in new_docs:
      prayer = doc.to_dict()
      prayer["id"] = doc.id
      prayers.append(prayer)
  except Exception as e:
    print(f"Error fetching personal prayers from new collection: {e}")

  return prayers


def get_all_personal_prayers_for_user(user_id=None) -> dict:
  """Fetches all personal prayers for user, grouped by category."""
  prayers_by_cat_with_prayers = {}

  target_id = user_id
  if target_id is None and flask_login.current_user.is_authenticated:
    target_id = flask_login.current_user.id

  if target_id:
    raw_prayers = fetch_personal_prayers(target_id)
    temp_prayers = {}  # category -> list

    for prayer in raw_prayers:
      category = prayer.get("category")
      if category:
        if category not in temp_prayers:
          temp_prayers[category] = []
        prayer["text"] = decrypt_text(prayer["text"])
        if prayer.get("for_whom"):
          prayer["for_whom"] = decrypt_text(prayer["for_whom"])
        temp_prayers[category].append(prayer)

    for category in sorted(temp_prayers.keys()):
      if temp_prayers[category]:
        prayers_by_cat_with_prayers[category] = temp_prayers[category]

  return prayers_by_cat_with_prayers


def get_mid_week_reading_for_date(now: datetime.datetime) -> Optional[dict]:
  """Returns mid week reading data for given date based on week of church year."""
  cy = liturgy.ChurchYear(now.year)
  week_num = cy.get_week_of_church_year(now.date()) + 1

  max_week = 53
  try:
    max_week = max(
        r["week_number"]
        for r in MID_WEEK_READINGS["extended_mid_week_devotions"]
    )
  except (KeyError, ValueError):
    pass

  if week_num > max_week:
    week_num = 1

  for reading in MID_WEEK_READINGS["extended_mid_week_devotions"]:
    if reading["week_number"] == week_num:
      return reading
  return None


def save_bia_progress(user_id: str, day: int, last_visit_str: str):
  """Saves Bible in a Year progress for a user."""
  db = get_db_client()
  user_ref = db.collection("users").document(user_id)
  user_ref.set(
      {"bia_progress": {"current_day": day, "last_visit_str": last_visit_str}},
      merge=True,
  )


def get_bible_in_a_year_devotion_data(user_id=None, date_obj=None):
  """Generates data for the Bible in a Year devotion for email/reminders."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = date_obj or datetime.datetime.now(eastern_timezone)
  bible_in_a_year_data = load_bible_in_a_year_data()

  current_day = now.timetuple().tm_yday  # Default to day of year

  if user_id:
    db = get_db_client()
    doc = db.collection("users").document(user_id).get()
    if doc.exists:
      user_data = doc.to_dict()
      if user_data:
        bia_progress = user_data.get("bia_progress")
        if bia_progress and "current_day" in bia_progress:
          current_day = int(bia_progress["current_day"])

  # Ensure day is within range 1-365
  current_day = max(1, min(current_day, 365))

  day_data = bible_in_a_year_data[current_day - 1]

  ot_ref = day_data["Old Testament"]
  nt_ref = day_data["New Testament"]
  psp_ref = day_data["Psalms & Proverbs"]

  try:
    texts = fetch_passages([ot_ref, nt_ref, psp_ref])
    ot_text = texts[0]
    nt_text = texts[1]
    psp_text = texts[2]
  except Exception as e:
    print(f"Error fetching passages for Bible in a Year: {e}")
    ot_text = "Text not available"
    nt_text = "Text not available"
    psp_text = "Text not available"

  return {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "day_number": current_day,
      "ot_ref": ot_ref,
      "ot_text": ot_text,
      "nt_ref": nt_ref,
      "nt_text": nt_text,
      "psp_ref": psp_ref,
      "psp_text": psp_text,
  }


def get_office_devotion_data(user_id, office_name, date_obj=None):
  """Generates data for an office devotion (Morning, Evening, etc.)."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = date_obj or datetime.datetime.now(eastern_timezone)
  cy = liturgy.ChurchYear(now.year)
  key = cy.get_liturgical_key(now)

  readings_key = f"{office_name}_readings"
  psalms_key = f"{office_name}_psalms"

  reading_ref = get_deterministic_choice(OFFICE_READINGS[readings_key], now)
  psalm_options = OFFICE_READINGS.get(psalms_key, [])
  psalm_ref = get_deterministic_choice(psalm_options, now)

  # Daily Lectionary
  lectionary_data = load_lectionary(LECTIONARY_JSON_PATH)
  l_readings = lectionary_data.get(
      key, {"OT": "Reading not found", "NT": "Reading not found"}
  )
  daily_lectionary_readings = [
      r
      for r in [l_readings["OT"], l_readings["NT"]]
      if r != "Reading not found"
  ]

  # Bible in a Year
  bible_in_a_year_data = get_bible_in_a_year_devotion_data(user_id, now)

  all_refs = [reading_ref, psalm_ref] + daily_lectionary_readings
  all_texts = fetch_passages(all_refs)
  reading_text = all_texts[0]
  psalm_text = all_texts[1]
  lectionary_texts = all_texts[2:]

  # Base data
  data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "key": key,
      "is_trinity_sunday": now.date() == cy.holy_trinity,
      "daily_lectionary_readings": daily_lectionary_readings,
      "lectionary_texts": lectionary_texts,
      "bible_in_a_year_reading": bible_in_a_year_data,
      "reading_ref": reading_ref,
      "reading_options": OFFICE_READINGS[readings_key],
      "reading_text": reading_text,
      "psalm_ref": psalm_ref,
      "psalm_options": psalm_options,
      "psalm_text": psalm_text,
  }

  # Add Catechism if enabled and not Night Watch (which usually doesn't have it)
  if office_name != "night_watch":
    catechism_data = get_catechism_for_day(now, rotation="daily")
    data.update(catechism_data)

  # Add Concluding Prayer
  concluding_prayer_key = f"{office_name}_prayers"
  if concluding_prayer_key in OTHER_PRAYERS:
    data["concluding_prayer"] = OTHER_PRAYERS[concluding_prayer_key]

  # Add Personal Prayers if logged in
  all_personal_prayers = get_all_personal_prayers_for_user(user_id)
  data["all_personal_prayers"] = all_personal_prayers

  # Specific prayers for certain offices
  if office_name == "morning":
    data["luthers_morning_prayer"] = OTHER_PRAYERS["luthers_morning_prayer"]
  elif office_name == "close_of_day":
    data["luthers_evening_prayer"] = OTHER_PRAYERS["luthers_evening_prayer"]
    # Weekly prayer topic for Close of Day
    weekly_prayer_data = get_weekly_prayer_for_day(now, user_id)
    data.update(weekly_prayer_data)
  elif office_name == "night_watch":
    data["protection_prayer"] = OTHER_PRAYERS["night_watch_protection_prayers"]
    data["concluding_prayer"] = OTHER_PRAYERS["night_watch_concluding_prayers"]

  return data
