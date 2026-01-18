"""Functions for generating the morning devotion."""

import flask
import flask_login
import utils


def get_morning_devotion_data(user_id=None):
  """Generates data for the morning devotion."""
  return utils.get_office_devotion_data(user_id, "morning")


def generate_morning_devotion():
  """Generates HTML for the morning devotion for the current date."""
  user_id = None
  if flask_login.current_user.is_authenticated:
    user_id = flask_login.current_user.id
  template_data = get_morning_devotion_data(user_id)
  print("Generated Morning HTML")
  return flask.render_template("morning_devotion.html", **template_data)
