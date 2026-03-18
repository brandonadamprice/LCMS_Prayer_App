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

  # Support ?date=YYYY-MM-DD query param if no date_obj provided
  if date_obj is None:
    date_str_param = flask.request.args.get("date")
    if date_str_param:
      try:
        now = datetime.datetime.strptime(date_str_param, "%Y-%m-%d")
      except ValueError:
        pass

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

  today = datetime.datetime.now(eastern_timezone).date()
  prev_date = (now.date() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
  next_day = now.date() + datetime.timedelta(days=1)
  next_date = next_day.strftime("%Y-%m-%d") if next_day <= today else None

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "key": key,
      "prev_date": prev_date,
      "next_date": next_date,
      "ot_ref": readings["OT"],
      "ot_text": texts[0],
      "nt_ref": readings["NT"],
      "nt_text": texts[1],
  }

  print("Generated Daily Lectionary HTML")
  return flask.render_template("daily_lectionary.html", **template_data)
