"""Functions for generating the evening devotion."""

import flask
import flask_login
import utils


def get_evening_devotion_data(user_id=None, date_obj=None):
  """Generates data for the evening devotion."""
  return utils.get_office_devotion_data(user_id, "evening", date_obj)


def generate_evening_devotion(date_obj=None):
  """Generates HTML for the evening devotion for the current date."""
  user_id = None
  if flask_login.current_user.is_authenticated:
    user_id = flask_login.current_user.id
  template_data = get_evening_devotion_data(user_id, date_obj)
  print("Generated Evening HTML")
  return flask.render_template("evening_devotion.html", **template_data)
