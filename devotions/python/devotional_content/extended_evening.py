"""Functions for generating the evening devotion."""

import datetime
import flask
import flask_login
import pytz
import utils


def generate_extended_evening_devotion(date_obj=None):
  """Generates HTML for the evening devotion for the current date.

  This function fetches lectionary readings, a psalm, and a catechism section
  based on the current date, combines them with a weekly prayer topic, and
  renders an HTML page.

  Returns:
      The generated HTML as a string.
  """
  eastern_timezone = pytz.timezone("America/New_York")
  now = date_obj or datetime.datetime.now(eastern_timezone)

  user_id = (
      flask_login.current_user.id
      if flask_login.current_user.is_authenticated
      else None
  )

  template_data = utils.get_devotion_data(now, user_id=user_id)
  template_data["concluding_prayer"] = utils.OTHER_PRAYERS[
      "close_of_day_prayers"
  ]
  template_data["luthers_evening_prayer"] = utils.OTHER_PRAYERS[
      "luthers_evening_prayer"
  ]

  print("Generated Evening HTML")
  return flask.render_template(
      "extended_evening_devotion.html", **template_data
  )
