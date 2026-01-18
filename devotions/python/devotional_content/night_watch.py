"""Functions for generating the Night Watch devotion."""

import flask
import flask_login
import utils


def get_night_watch_devotion_data(user_id=None):
  """Generates data for the Night Watch devotion."""
  return utils.get_office_devotion_data(user_id, "night_watch")


def generate_night_watch_devotion():
  """Generates HTML for the Night Watch devotion."""
  user_id = None
  if flask_login.current_user.is_authenticated:
    user_id = flask_login.current_user.id
  template_data = get_night_watch_devotion_data(user_id)
  print("Generated Night Watch HTML")
  return flask.render_template("night_watch_devotion.html", **template_data)
