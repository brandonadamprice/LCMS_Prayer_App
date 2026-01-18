"""Functions for generating the close of day devotion."""

import flask
import utils


def get_close_of_day_devotion_data(user_id=None):
  """Generates data for the close of day devotion."""
  return utils.get_office_devotion_data(user_id, "close_of_day")


def generate_close_of_day_devotion():
  """Generates HTML for the close of day devotion for the current date."""
  template_data = get_close_of_day_devotion_data()
  print("Generated Close of Day HTML")
  return flask.render_template("close_of_day_devotion.html", **template_data)
