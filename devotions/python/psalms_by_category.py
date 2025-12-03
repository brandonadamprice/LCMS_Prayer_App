"""Functions for generating the Psalms by Category page."""

import json
import os
import random
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
  categories = load_psalms_by_category()
  psalm_refs = []
  for cat in categories:
    psalm_num = random.choice(cat["Psalms"])
    psalm_refs.append(f"Psalm {psalm_num}")

  psalm_texts = utils.fetch_passages(psalm_refs)

  # Combine data for easier looping in Jinja2
  category_data = []
  for i, cat in enumerate(categories):
    category_data.append({
        "title": cat["title"],
        "description": cat["description"],
        "psalms": cat["Psalms"],
        "prayer": cat["prayer"],
        "initial_psalm_ref": psalm_refs[i],
        "initial_psalm_text": psalm_texts[i],
    })

  print("Generated Psalms by Category HTML")
  return flask.render_template(
      "psalms_by_category.html", category_data=category_data
  )
