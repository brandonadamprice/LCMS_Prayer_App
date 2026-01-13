"""Functions for generating the Psalms by Category page."""

import json
import os
import flask
import utils

PSALMS_BY_CATEGORY_JSON_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "psalms_by_category.json"
)


def load_psalms_by_category():
  """Loads Psalms by category from JSON file."""
  with open(PSALMS_BY_CATEGORY_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def generate_psalms_by_category_page():
  """Generates HTML for the Psalms by Category page."""
  category_data = utils.generate_category_page_data(
      PSALMS_BY_CATEGORY_JSON_PATH
  )

  print("Generated Psalms by Category HTML")
  return flask.render_template(
      "psalms_by_category.html", category_data=category_data
  )
