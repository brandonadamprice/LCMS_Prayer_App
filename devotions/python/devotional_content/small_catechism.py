"""Functions for generating the Small Catechism page."""

import flask
import utils


def get_grouped_catechism():
  """Groups the catechism sections into the Six Chief Parts."""
  sections = utils.CATECHISM_SECTIONS
  groups = {
      "The Ten Commandments": [],
      "The Apostles' Creed": [],
      "The Lord's Prayer": [],
      "The Sacrament of Holy Baptism": [],
      "Confession": [],
      "The Sacrament of the Altar": [],
      "Daily Prayers": [],
      "Table of Duties": [],
      "Christian Questions with Their Answers": [],
  }

  for section in sections:
    title = section["title"]
    if "Commandment" in title or "Close of the Commandments" in title:
      groups["The Ten Commandments"].append(section)
    elif "Creed" in title:
      groups["The Apostles' Creed"].append(section)
    elif "Lord's Prayer" in title:
      groups["The Lord's Prayer"].append(section)
    elif "Baptism" in title:
      groups["The Sacrament of Holy Baptism"].append(section)
    elif "Confession" in title or "Office of the Keys" in title:
      groups["Confession"].append(section)
    elif "Sacrament of the Altar" in title:
      groups["The Sacrament of the Altar"].append(section)
    elif title in [
        "Morning Prayer",
        "Evening Prayer",
        "Asking a Blessing",
        "Returning Thanks",
    ]:
      groups["Daily Prayers"].append(section)
    elif "Table of Duties" in title:
      groups["Table of Duties"].append(section)
    elif "Christian Questions" in title:
      groups["Christian Questions with Their Answers"].append(section)
    else:
      # Fallback for any unmatched sections
      if "Other" not in groups:
        groups["Other"] = []
      groups["Other"].append(section)

  # Filter out empty groups and return
  return {k: v for k, v in groups.items() if v}


def generate_small_catechism_page():
  """Generates HTML for the Small Catechism page."""
  grouped_catechism = get_grouped_catechism()

  print("Generated Small Catechism HTML")
  return flask.render_template(
      "small_catechism.html",
      grouped_catechism=grouped_catechism,
  )
