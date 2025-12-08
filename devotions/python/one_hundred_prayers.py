"""Functions for generating the 100 Prayers page."""

import json
import os
import flask
import utils

ONE_HUNDRED_PRAYERS_JSON_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "100_prayers.json"
)


def load_100_prayers_data():
  """Loads 100 prayers data from JSON file."""
  with open(ONE_HUNDRED_PRAYERS_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def generate_100_prayers_page():
  """Generates HTML for the 100 Prayers page."""
  data = load_100_prayers_data()
  template_data = {"situations": data["prayers_for_specific_situations"]}
  print("Generated 100 Prayers HTML")
  return flask.render_template("100_prayers.html", **template_data)
