"""Functions for generating the Psalms by Category page."""

import os
import flask
import utils

PSALMS_BY_CATEGORY_JSON_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "psalms_by_category.json"
)


def generate_psalms_by_category_page():
  """Generates HTML for the Psalms by Category page."""
  category_data = utils.generate_category_page_data(
      PSALMS_BY_CATEGORY_JSON_PATH
  )

  return flask.render_template(
      "psalms_by_category.html", category_data=category_data
  )
