"""Functions for generating the Trinity study page."""

import json
import os
from functools import lru_cache

import flask
import utils

TRINITY_STUDY_JSON_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "trinity.json"
)


@lru_cache(maxsize=1)
def load_trinity_study_data():
  """Loads and processes Trinity study data from JSON file."""
  with open(TRINITY_STUDY_JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)
  return utils.process_node(data)


def generate_trinity_study_page():
  """Generates HTML for the Trinity study page."""
  study_data = load_trinity_study_data()
  template_data = study_data["study_of_the_holy_trinity"]
  print("Generated Trinity Study HTML")
  return flask.render_template("trinity_study.html", study=template_data)
