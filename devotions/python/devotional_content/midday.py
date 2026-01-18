"""Functions for generating the midday devotion."""

import flask
import flask_login
import utils


def get_midday_devotion_data(user_id=None):
  """Generates data for the midday devotion."""
  return utils.get_office_devotion_data(user_id, "midday")


def generate_midday_devotion():
  """Generates HTML for the midday devotion for the current date."""
  user_id = None
  if flask_login.current_user.is_authenticated:
    user_id = flask_login.current_user.id
  template_data = get_midday_devotion_data(user_id)
  print("Generated Midday HTML")
  return flask.render_template("midday_devotion.html", **template_data)
