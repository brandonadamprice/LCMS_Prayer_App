"""Functions for generating the children's devotion."""

import datetime
import flask
import pytz
import utils


def get_ten_commandments():
  """Returns a list of the text of the 10 commandments."""
  commandments = []
  for i in range(10):
    commandments.append(utils.CATECHISM_SECTIONS[i])
  return commandments


def generate_childrens_devotion():
  """Generates HTML for the children's devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  catechism_data = utils.get_catechism_for_day(now, rotation="daily")

  ten_commandments = get_ten_commandments()

  template_data = {
      "ten_commandments": ten_commandments,
      "apostles_creed": utils.OTHER_PRAYERS["apostles_creed"],
      "lords_prayer": utils.OTHER_PRAYERS["lords_prayer"],
      "childs_daily_petition": utils.OTHER_PRAYERS["childs_daily_petition"],
  }
  template_data.update(catechism_data)

  print("Generated Children's Devotion HTML")
  return flask.render_template("childrens_devotion.html", **template_data)
