"""Functions for generating the midday devotion."""

import flask
import flask_login
import utils


def get_midday_devotion_data(user_id=None, date_obj=None):
  """Generates data for the midday devotion."""
  return utils.get_office_devotion_data(user_id, "midday", date_obj)


def generate_midday_devotion(date_obj=None):
  """Generates HTML for the midday devotion for the current date."""
  user_id = None
  if flask_login.current_user.is_authenticated:
    user_id = flask_login.current_user.id
  template_data = get_midday_devotion_data(user_id, date_obj)
  print("Generated Midday HTML")
  return flask.render_template("midday_devotion.html", **template_data)
