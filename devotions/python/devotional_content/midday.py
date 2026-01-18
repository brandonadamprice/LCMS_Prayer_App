"""Functions for generating the midday devotion."""

import flask
import utils


def get_midday_devotion_data(user_id=None):
  """Generates data for the midday devotion."""
  return utils.get_office_devotion_data(user_id, "midday")


def generate_midday_devotion():
  """Generates HTML for the midday devotion for the current date."""
  template_data = get_midday_devotion_data()
  print("Generated Midday HTML")
  return flask.render_template("midday_devotion.html", **template_data)
