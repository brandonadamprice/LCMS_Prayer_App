"""Functions for generating the Small Catechism page."""

import copy
import json
import os
import re
import flask
import flask_login
import utils

CATECHISM_EXPLANATION_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "catechism_explaination.json"
)


def load_catechism_explanation():
  """Loads the catechism explanation data."""
  try:
    with open(CATECHISM_EXPLANATION_PATH, "r", encoding="utf-8") as f:
      data = json.load(f)
      return utils.process_node(data)
  except FileNotFoundError:
    print(f"Warning: {CATECHISM_EXPLANATION_PATH} not found.")
    return {}


def get_grouped_catechism():
  """Groups the catechism sections into the Six Chief Parts."""
  # Deep copy to prevent modifying the global CATECHISM_SECTIONS in place,
  # which causes recursive tooltip injection on page reloads.
  sections = copy.deepcopy(utils.CATECHISM_SECTIONS)
  explanation_data = load_catechism_explanation()

  # Create a lookup for explanations by title
  explanations_map = {}
  christian_questions_data = {}

  # List of keys in explanation_data that contain lists of items with "title"
  keys_to_load = [
      "ten_commandments",
      "apostles_creed",
      "lords_prayer",
      "sacrament_of_holy_baptism",
      "confession_and_office_of_the_keys",
      "sacrament_of_the_altar",
      "daily_prayers",
      "table_of_duties",
      "christian_questions_and_answers",
  ]

  for key in keys_to_load:
    if key in explanation_data:
      for item in explanation_data[key]:
        if "title" in item:
          explanations_map[item["title"]] = item
        elif "question_number" in item:
          christian_questions_data[item["question_number"]] = item

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

  for idx, section in enumerate(sections):
    title = section["title"]
    section["index"] = idx  # Add original index for tracking

    # Inject explanation data if available
    if title in explanations_map:
      section["explanation"] = explanations_map[title]["explanation"]
      section["quiz_questions"] = explanations_map[title]["questions"]

    # Special handling for Christian Questions per-question explanation
    if "Christian Questions" in title and "questions_and_answers" in section:
      for i, qa in enumerate(section["questions_and_answers"]):
        q_num = i + 1
        if q_num in christian_questions_data:
          cq_item = christian_questions_data[q_num]
          qa["explanation"] = cq_item.get("explanation", "")
          qa["quiz_questions"] = cq_item.get("questions", [])

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
  completed_sections = []

  if flask_login.current_user.is_authenticated:
    completed_sections = flask_login.current_user.completed_catechism_sections

  print("Generated Small Catechism HTML")
  return flask.render_template(
      "small_catechism.html",
      grouped_catechism=grouped_catechism,
      completed_sections=completed_sections,
  )
