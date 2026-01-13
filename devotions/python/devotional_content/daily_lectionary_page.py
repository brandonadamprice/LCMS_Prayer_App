"""Functions for generating the Daily Lectionary page."""

import datetime
import logging
import re
import flask
import pytz
from services import fullofeyes_scraper
import utils

logger = logging.getLogger(__name__)


def generate_daily_lectionary_page():
  """Generates HTML for the Daily Lectionary page."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)

  # Reuse utils logic to get key and readings
  cy = utils.ChurchYear(now.year)
  key = cy.get_liturgical_key(now)

  data = utils.load_lectionary(utils.LECTIONARY_JSON_PATH)
  readings = data.get(
      key, {"OT": "Reading not found", "NT": "Reading not found"}
  )

  # Fetch texts
  refs = [readings["OT"], readings["NT"]]
  texts = utils.fetch_passages(refs)

def get_art_for_reading(reading_ref):
  """Searches for art based on a scripture reference."""
  if not reading_ref or reading_ref == "Reading not found":
    return None

  queries_to_try = []

  # 1. Base query: Book + Chapter (e.g., "Romans 4" from "Romans 4:1-25")
  if ":" in reading_ref:
    base_query = reading_ref.split(":")[0].strip()
    queries_to_try.append(base_query)

    # 2. Fallback: Book Name only (e.g., "Romans" from "Romans 4")
    # Remove the chapter number at the end
    book_match = re.match(r"^(.*?)\s+\d+$", base_query)
    if book_match:
      queries_to_try.append(book_match.group(1).strip())
  else:
    # Handle cases like "Jude 1-25" or "Obadiah 1" (no colon)
    # Try to capture "Jude 1" then "Jude"
    match = re.match(r"^(.*)\s+([\d\-]+)$", reading_ref)
    if match:
      book_name = match.group(1).strip()
      # If the second part contains digits, try Book + 1 as well as Book
      queries_to_try.append(f"{book_name} 1")
      queries_to_try.append(book_name)
    else:
      # Just try the whole thing if we can't parse it
      queries_to_try.append(reading_ref)

  # Remove duplicates while preserving order
  queries_to_try = list(dict.fromkeys(queries_to_try))

  logger.info(
      f"Searching art for ref '{reading_ref}' with queries: {queries_to_try}"
  )

  for query in queries_to_try:
    results = fullofeyes_scraper.search_images_cached(query)
    if results:
      logger.info(f"Found art for query '{query}'")
      return results[0]

  logger.info("No art found.")
  return None

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "key": key,
      "ot_ref": readings["OT"],
      "ot_text": texts[0],
      "nt_ref": readings["NT"],
      "nt_text": texts[1],
  }

  print("Generated Daily Lectionary HTML")
  return flask.render_template("daily_lectionary.html", **template_data)
