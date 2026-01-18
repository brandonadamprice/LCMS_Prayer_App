"""Functions for generating the Night Watch devotion."""

import flask
import utils


def get_night_watch_devotion_data(user_id=None):
  """Generates data for the Night Watch devotion."""
  return utils.get_office_devotion_data(user_id, "night_watch")


def generate_night_watch_devotion():
  """Generates HTML for the Night Watch devotion."""
  template_data = get_night_watch_devotion_data()
  print("Generated Night Watch HTML")
  return flask.render_template("night_watch_devotion.html", **template_data)
