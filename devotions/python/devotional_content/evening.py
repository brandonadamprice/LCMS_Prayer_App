"""Functions for generating the evening devotion."""

import flask
import utils


def get_evening_devotion_data(user_id=None):
  """Generates data for the evening devotion."""
  return utils.get_office_devotion_data(user_id, "evening")


def generate_evening_devotion():
  """Generates HTML for the evening devotion for the current date."""
  template_data = get_evening_devotion_data()
  print("Generated Evening HTML")
  return flask.render_template("evening_devotion.html", **template_data)
