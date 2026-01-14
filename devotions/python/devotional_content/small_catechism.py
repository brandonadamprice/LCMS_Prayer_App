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

  # Also fetch Daily Prayers from other_prayers.json to present as a section
  daily_prayers_data = []
  op = utils.OTHER_PRAYERS

  # Mapping keys to display titles for standard Catechism Daily Prayers
  dp_keys = [
      ("luthers_morning_prayer", "Morning Prayer"),
      ("luthers_evening_prayer", "Evening Prayer"),
      (
          "childs_daily_petition",
          "Asking a Blessing",
      ),  # Using this as a placeholder for Tischgebet/Blessing? No, let's just stick to what we have.
  ]

  # Construct a pseudo-section for Daily Prayers
  daily_prayers_section = {"group_title": "Daily Prayers", "items": []}

  for key, title in dp_keys:
    if key in op:
      daily_prayers_section["items"].append({
          "title": title,
          "text": op[key]["prayer"],
          "reference": op[key].get("reference"),
      })

  print("Generated Small Catechism HTML")
  return flask.render_template(
      "small_catechism.html",
      grouped_catechism=grouped_catechism,
      daily_prayers=daily_prayers_section,
  )
