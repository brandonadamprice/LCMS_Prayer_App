"""Functions for generating the Mary study page."""

from functools import lru_cache
import json
import os

import flask
import utils

MARY_STUDY_JSON_PATH = os.path.join(utils.SCRIPT_DIR, "..", "data", "mary.json")


@lru_cache(maxsize=1)
def load_mary_study_data():
  """Loads Mary study data from JSON file."""
  with open(MARY_STUDY_JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)
  return utils.process_node(data)


def generate_mary_study_page():
  """Generates HTML for the Mary study page."""
  study_data = load_mary_study_data()
  template_data = study_data["mary_study"]
  return flask.render_template("mary_study.html", **template_data)
