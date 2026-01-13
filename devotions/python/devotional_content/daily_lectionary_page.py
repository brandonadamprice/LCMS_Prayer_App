"""Functions for generating the Daily Lectionary page."""

import datetime
import flask
import pytz
from services import fullofeyes_scraper
import utils


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

  # Try to fetch relevant art for the OT reading
  art_data = None
  try:
    ot_ref = readings["OT"]
    if ot_ref and ot_ref != "Reading not found":
      # Heuristic: Use Book + Chapter (e.g. "Isaiah 60:1-6" -> "Isaiah 60")
      # Split by ':' to get book and chapter
      query_parts = ot_ref.split(":")
      if query_parts:
        query = query_parts[0].strip()
        # Fallback if no colon (e.g. "Obadiah 1") or other format
        # If it's something like "Genesis 1", split might return "Genesis 1" which is fine.
        # Just ensure we strip verse ranges if any remain (though usually they are after colon).
        # Also clean up things like "1 Kings" vs "1Kings" if needed, but scraper handles search.

        if query:
          results = fullofeyes_scraper.search_images_cached(query)
          if results:
            art_data = results[0]
  except Exception as e:
    print(f"Error fetching art for daily lectionary: {e}")

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "key": key,
      "ot_ref": readings["OT"],
      "ot_text": texts[0],
      "nt_ref": readings["NT"],
      "nt_text": texts[1],
      "art_data": art_data,
  }

  print("Generated Daily Lectionary HTML")
  return flask.render_template("daily_lectionary.html", **template_data)
