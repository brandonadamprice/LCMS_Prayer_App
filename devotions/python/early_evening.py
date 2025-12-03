"""Functions for generating the early evening devotion."""

import datetime
import random
import flask
import pytz
import utils


def generate_early_evening_devotion():
  """Generates HTML for the early evening devotion for the current date."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  cy = utils.ChurchYear(now.year)
  key = cy.get_liturgical_key(now)
  day_of_year = now.timetuple().tm_yday
  cat_idx = day_of_year % len(utils.CATECHISM_SECTIONS)
  catechism = utils.CATECHISM_SECTIONS[cat_idx]
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

  reading_ref = random.choice(utils.OFFICE_READINGS["early_evening_readings"])
  psalm_num = random.randint(1, 150)
  psalm_ref = f"Psalm {psalm_num}"

  reading_text, psalm_text = utils.fetch_passages([reading_ref, psalm_ref])
  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "key": key,
      "reading_ref": reading_ref,
      "reading_text": reading_text,
      "psalm_ref": psalm_ref,
      "psalm_text": psalm_text,
      "catechism_title": catechism["title"],
      "catechism_text": catechism["text"],
      "catechism_meaning_html": catechism_meaning_html,
      "catechism_prayer": catechism_prayer,
  }

  print("Generated Early Evening HTML")
  return flask.render_template("early_evening_devotion.html", **template_data)
