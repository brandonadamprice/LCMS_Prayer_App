"""Functions for generating the children's devotion."""

import flask
import utils


def get_ten_commandments():
  """Returns a list of the text of the 10 commandments."""
  commandments = []
  for i in range(10):
    commandments.append(utils.CATECHISM_SECTIONS[i])
  return commandments


def generate_childrens_devotion():
  """Generates HTML for the children's devotion."""

  ten_commandments = get_ten_commandments()

  template_data = {
      "ten_commandments": ten_commandments,
      "apostles_creed": utils.OTHER_PRAYERS["apostles_creed"],
      "lords_prayer": utils.OTHER_PRAYERS["lords_prayer"],
      "childs_daily_petition": utils.OTHER_PRAYERS["childs_daily_petition"],
  }

  print("Generated Children's Devotion HTML")
  return flask.render_template("childrens_devotion.html", **template_data)
