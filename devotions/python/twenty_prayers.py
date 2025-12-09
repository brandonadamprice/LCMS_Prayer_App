"""Functions for generating the Short Prayers page."""

import json
import os
import flask
import utils

SHORT_PRAYERS_JSON_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "short_prayers.json"
)


def load_short_prayers_data():
  """Loads short prayers data from JSON file."""
  with open(SHORT_PRAYERS_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def generate_short_prayers_page():
  """Generates HTML for the Short Prayers page."""
  data = load_short_prayers_data()
  template_data = {"situations": data["prayers_for_specific_situations"]}
  print("Generated Short Prayers HTML")
  return flask.render_template("short_prayers.html", **template_data)
