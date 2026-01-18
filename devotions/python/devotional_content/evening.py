"""Functions for generating the evening devotion."""

import flask
import flask_login
import utils


def get_evening_devotion_data(user_id=None):
  """Generates data for the evening devotion."""
  return utils.get_office_devotion_data(user_id, "evening")


def generate_evening_devotion():
  """Generates HTML for the evening devotion for the current date."""
  user_id = None
  if flask_login.current_user.is_authenticated:
    user_id = flask_login.current_user.id
  template_data = get_evening_devotion_data(user_id)
  print("Generated Evening HTML")
  return flask.render_template("evening_devotion.html", **template_data)
