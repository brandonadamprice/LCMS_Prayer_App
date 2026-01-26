"""Functions for generating the Nicene Creed study page."""

from functools import lru_cache
import json
import os

import flask
import utils

NICENE_CREED_STUDY_JSON_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "nicene_creed_study.json"
)


@lru_cache(maxsize=1)
def load_nicene_creed_study_data():
  """Loads Nicene Creed study data from JSON file."""
  with open(NICENE_CREED_STUDY_JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)
  return utils.process_node(data)


def generate_nicene_creed_study_page():
  """Generates HTML for the Nicene Creed study page."""
  study_data = load_nicene_creed_study_data()
  template_data = study_data["nicene_creed_study"]
  print("Generated Nicene Creed Study HTML")
  return flask.render_template("nicene_creed_study.html", **template_data)
