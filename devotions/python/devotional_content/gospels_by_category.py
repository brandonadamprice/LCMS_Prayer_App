"""Functions for generating the Gospels by Category page."""

import os
import flask
import utils

GOSPELS_BY_CATEGORY_JSON_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "gospels_by_category.json"
)


def generate_gospels_by_category_page():
  """Generates HTML for the Gospels by Category page."""
  category_data = utils.generate_category_page_data(
      GOSPELS_BY_CATEGORY_JSON_PATH
  )

  return flask.render_template(
      "gospels_by_category.html", category_data=category_data
  )
