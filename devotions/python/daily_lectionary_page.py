"""Functions for generating the Daily Lectionary page."""

import datetime
import flask
import pytz
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
