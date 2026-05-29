"""Functions for generating the Prayer Weaver tool data."""

import json
import os
from functools import lru_cache

import flask
import utils

PRAYER_WEAVER_JSON_PATH = os.path.join(utils.SCRIPT_DIR, "..", "data", "prayer_weaver.json")

@lru_cache(maxsize=1)
def load_prayer_weaver_data():
  """Loads prayer weaver data from JSON file (cached; treat as read-only)."""
  with open(PRAYER_WEAVER_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)

def render_prayer_weaver_page():
  """Renders the Prayer Weaver tool page with data."""
  data = load_prayer_weaver_data()
  return flask.render_template("prayer_weaver.html", weaver_data=data)
