"""Shared utility functions and data for devotions."""

import csv
import datetime
import functools
import json
import os
import random
import re
from typing import Optional
import uuid

import cryptography.fernet
import flask_login
from google.cloud import firestore
from google.cloud.firestore_v1 import base_query
import requests
import secrets_fetcher as secrets

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


def load_mid_week_readings():
  """Loads mid week readings from JSON file."""
  with open(MID_WEEK_READINGS_JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)
    for item in data["extended_mid_week_devotions"]:
      item["church_season_day"] = item.pop("church_season/day")
    return data


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
  prayer = random.choice(catechism["prayers"])
  return {
      "catechism_enabled": True,
      "catechism_title": catechism["title"],
      "catechism_text": catechism["text"],
      "questions_and_answers": catechism["questions_and_answers"],
      "catechism_prayer": prayer,
  }


def get_weekly_prayer_for_day(now: datetime.datetime) -> dict:
  """Returns the weekly prayer topic and text for a given day."""
  weekday_idx = now.weekday()
  prayer_data = WEEKLY_PRAYERS.get(
      str(weekday_idx), {"topic": "General Intercessions", "prayer": ""}
  )
  topic = prayer_data["topic"]
  personal_prayers_list = []
  if flask_login.current_user.is_authenticated:
    raw_prayers = fetch_personal_prayers(flask_login.current_user.id)
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
    self.septuagesima = self.easter_date - datetime.timedelta(days=63)
    self.sexagesima = self.easter_date - datetime.timedelta(days=56)
    self.quinquagesima = self.easter_date - datetime.timedelta(days=49)

  def calculate_advent1(self, year: int) -> datetime.date:
    """Advent 1 is the Sunday between Nov 27 and Dec 3."""
    return datetime.date(year, 12, 3) - datetime.timedelta(
        days=(datetime.date(year, 12, 3).weekday() + 1) % 7
    )

  def get_week_of_church_year(self, current_date: datetime.date) -> int:
    """Returns week number 1-52 within church year starting Advent 1."""
    adv1_this_year = self.calculate_advent1(current_date.year)
    if current_date >= adv1_this_year:
      start_of_cy = adv1_this_year
    else:
      start_of_cy = self.calculate_advent1(current_date.year - 1)

    week = ((current_date - start_of_cy).days // 7) % 52 + 1
    return week

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
  catechism_data = get_catechism_for_day(now, rotation="daily")
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
def _fetch_passages_cached(
    references: tuple[str, ...],
    include_verse_numbers: bool = True,
    include_copyright: bool = True,
) -> tuple[str, ...]:
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
      "include-verse-numbers": str(include_verse_numbers).lower(),
      "include-passage-references": "false",
      "include-chapter-numbers": "false",
      "include-copyright": str(include_copyright).lower(),
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
              if len(passages_list) > 1 and include_copyright:
                processed_passages = [
                    p.strip().removesuffix(" (ESV)") for p in passages_list[:-1]
                ]
                processed_passages.append(passages_list[-1].strip())
                text_block = " ".join(processed_passages)
              else:
                text_block = " ".join(p.strip() for p in passages_list)

              if include_copyright and text_block.endswith(" (ESV)"):
                text_block = (
                    text_block.removesuffix(" (ESV)")
                    + ' <span class="esv-attribution">(<a'
                    ' href="http://www.esv.org">ESV</a>)</span>'
                )
              elif not include_copyright and text_block.endswith(" (ESV)"):
                text_block = text_block.removesuffix(" (ESV)")
            else:
              text_block = ""

            if include_verse_numbers:
              text_block = re.sub(
                  r"\[(\d+)\]", r"<br><sup>\1</sup>", text_block
              )
              if text_block.startswith("<br>"):
                text_block = text_block[4:]
            else:
              text_block = re.sub(r"\[\d+\]", "", text_block).strip()

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


def fetch_passages(
    references: list[str],
    include_verse_numbers: bool = True,
    include_copyright: bool = True,
) -> list[str]:
  """Fetches multiple passages from api.esv.org in one request."""
  return list(
      _fetch_passages_cached(
          tuple(references), include_verse_numbers, include_copyright
      )
  )


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


def get_all_personal_prayers_for_user() -> dict:
  """Fetches all personal prayers for user, grouped by category."""
  prayers_by_cat_with_prayers = {}
  if flask_login.current_user.is_authenticated:
    raw_prayers = fetch_personal_prayers(flask_login.current_user.id)
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
  cy = ChurchYear(now.year)
  week_num = cy.get_week_of_church_year(now.date())

  for reading in MID_WEEK_READINGS["extended_mid_week_devotions"]:
    if reading["week_number"] == week_num:
      return reading
  return None


def get_analytics_user(db, visitor_id, ip_hash, current_user):
  """Finds or creates an analytics user based on visitor_id/cookie or login."""
  updates = {}

  users_col = db.collection("analytics_users")

  if current_user.is_authenticated:
    # 1. Try finding by Google ID
    query = users_col.where("google_id", "==", current_user.id).limit(1)
    docs = list(query.stream())
    if docs:
      user_ref = docs[0].reference
      user_data = docs[0].to_dict()
      user_id = docs[0].id

      # Link current visitor_id to this user if not already present
      existing_ids = user_data.get("visitor_ids", [])
      if visitor_id and visitor_id not in existing_ids:
        updates["visitor_ids"] = firestore.ArrayUnion([visitor_id])

      # Add IP hash if new
      existing_hashes = user_data.get("ip_hashes", [])
      if ip_hash not in existing_hashes:
        updates["ip_hashes"] = firestore.ArrayUnion([ip_hash])

      # Ensure email is up to date
      if user_data.get("email") != current_user.email:
        updates["email"] = current_user.email

    else:
      # 2. Not found by Google ID.
      # Check if an anonymous user exists with this visitor_id
      if visitor_id:
        query_anon = users_col.where(
            filter=base_query.FieldFilter(
                "visitor_ids", "array_contains", visitor_id
            )
        ).limit(1)
        anon_docs = list(query_anon.stream())
      else:
        anon_docs = []

      if anon_docs:
        # Upgrade anonymous user to logged-in user
        user_ref = anon_docs[0].reference
        user_data = anon_docs[0].to_dict()
        user_id = anon_docs[0].id

        if not user_data.get("google_id"):
          updates["google_id"] = current_user.id
          updates["email"] = current_user.email
        elif user_data.get("google_id") != current_user.id:
          # Conflict: This cookie is used by another user. Create new user.
          user_id = uuid.uuid4().hex
          user_ref = users_col.document(user_id)
          user_ref.set({
              "google_id": current_user.id,
              "email": current_user.email,
              "visitor_ids": [visitor_id] if visitor_id else [],
              "ip_hashes": [ip_hash],
              "created_at": firestore.SERVER_TIMESTAMP,
              "last_seen": firestore.SERVER_TIMESTAMP,
          })
          return user_id
      else:
        # Create new logged-in user
        user_id = uuid.uuid4().hex
        user_ref = users_col.document(user_id)
        user_ref.set({
            "google_id": current_user.id,
            "email": current_user.email,
            "visitor_ids": [visitor_id] if visitor_id else [],
            "ip_hashes": [ip_hash],
            "created_at": firestore.SERVER_TIMESTAMP,
            "last_seen": firestore.SERVER_TIMESTAMP,
        })
        return user_id

  else:
    # Anonymous User
    if not visitor_id:
      # Should ideally not happen if cookie logic works, but fallback to creating new
      visitor_id = str(uuid.uuid4())

    # Try finding by visitor_id
    # We do NOT fallback to IP hash lookup for anonymous users anymore,
    # to avoid merging different devices on the same network (e.g. WiFi).
    query = users_col.where(
        filter=base_query.FieldFilter(
            "visitor_ids", "array_contains", visitor_id
        )
    ).limit(1)
    docs = list(query.stream())

    if docs:
      user_ref = docs[0].reference
      user_data = docs[0].to_dict()
      user_id = docs[0].id

      # Add IP hash if new
      if ip_hash not in user_data.get("ip_hashes", []):
        updates["ip_hashes"] = firestore.ArrayUnion([ip_hash])

    else:
      # Create new anonymous user
      user_id = uuid.uuid4().hex
      user_ref = users_col.document(user_id)
      user_ref.set({
          "visitor_ids": [visitor_id],
          "ip_hashes": [ip_hash],
          "created_at": firestore.SERVER_TIMESTAMP,
          "last_seen": firestore.SERVER_TIMESTAMP,
      })
      return user_id

  # Perform updates if found
  if updates:
    updates["last_seen"] = firestore.SERVER_TIMESTAMP
    user_ref.update(updates)
  else:
    user_ref.update({"last_seen": firestore.SERVER_TIMESTAMP})

  return user_id


def cleanup_analytics():
  """Cleans up old analytics data and untracked paths."""
  db = get_db_client()
  today = datetime.date.today()
  cutoff_date = today - datetime.timedelta(days=30)

  # 1. Delete old daily_analytics
  docs = db.collection("daily_analytics").stream()
  active_users = set()

  for doc in docs:
    try:
      doc_date = datetime.datetime.strptime(doc.id, "%Y-%m-%d").date()
    except ValueError:
      # Skip malformed IDs or handle as needed
      continue

    if doc_date < cutoff_date:
      doc.reference.delete()
      continue

    # 2. Filter paths
    data = doc.to_dict()
    visits = data.get("visits", {})
    modified = False
    uids_to_remove = []

    for uid, visit_data in visits.items():
      paths = visit_data.get("paths", [])
      timestamps = visit_data.get("timestamps", [])

      new_paths = []
      new_timestamps = []

      # Assume paths and timestamps are parallel arrays
      for i in range(len(paths)):
        if i < len(timestamps):
          p = paths[i]
          t = timestamps[i]
          if p != "/tasks/send_reminders":
            new_paths.append(p)
            new_timestamps.append(t)

      if len(new_paths) != len(paths):
        modified = True
        if not new_paths:
          uids_to_remove.append(uid)
        else:
          visits[uid]["paths"] = new_paths
          visits[uid]["timestamps"] = new_timestamps
          active_users.add(uid)
      else:
        # No change, user is active if they have paths
        if paths:
          active_users.add(uid)
        else:
          uids_to_remove.append(uid)
          modified = True

    for uid in uids_to_remove:
      del visits[uid]
      modified = True

    if modified:
      doc.reference.update({"visits": visits})

  # 3. Cleanup users
  users_ref = db.collection("analytics_users")
  user_docs = users_ref.stream()
  deleted_users_count = 0

  for user_doc in user_docs:
    if user_doc.id not in active_users:
      user_doc.reference.delete()
      deleted_users_count += 1

  return deleted_users_count


def check_and_run_analytics_cleanup():
  """Runs analytics cleanup if it hasn't been run today.

  Returns:
      bool: True if cleanup was run, False otherwise.
  """
  db = get_db_client()
  today_str = datetime.date.today().isoformat()
  metadata_ref = db.collection("system_metadata").document("analytics_cleanup")

  snapshot = metadata_ref.get()
  if snapshot.exists:
    data = snapshot.to_dict()
    if data and data.get("last_run_date") == today_str:
      return False

  cleanup_analytics()
  metadata_ref.set({"last_run_date": today_str})
  return True
