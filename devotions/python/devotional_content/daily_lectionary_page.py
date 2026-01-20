"""Functions for generating the Daily Lectionary page."""

import datetime
import logging
import flask
import liturgy
import pytz
import utils

logger = logging.getLogger(__name__)


def generate_daily_lectionary_page(date_obj=None):
  """Generates HTML for the Daily Lectionary page."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = date_obj or datetime.datetime.now(eastern_timezone)

  # Use liturgical calendar logic to get key and utils to fetch readings
  cy = liturgy.ChurchYear(now.year)
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
