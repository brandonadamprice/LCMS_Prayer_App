"""Functions for generating the Bible in a Year page."""

import json
import flask
import utils


def generate_bible_in_a_year_page(
    bia_progress=None, completed_days=None, bible_streak=0
):
  """Generates HTML for the Bible in a Year page."""
  bible_in_a_year_data = utils.load_bible_in_a_year_data()

  # Pass all schedule data to the template.
  # The client-side JavaScript will handle day progression
  # and fetching readings via /get_passage_text.

  template_data = {
      "schedule": json.dumps(bible_in_a_year_data),
      "bia_progress": json.dumps(bia_progress) if bia_progress else "null",
      "completed_days": json.dumps(completed_days) if completed_days else "[]",
      "bible_streak": bible_streak,
  }

  print("Generated Bible in a Year HTML")
  return flask.render_template("bible_in_a_year.html", **template_data)
