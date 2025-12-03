"""Functions for generating the Gospels by Category page."""

import json
import os
import random
import flask
import utils

GOSPELS_BY_CATEGORY_JSON_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "gospels_by_category.json"
)


def load_gospels_by_category():
  """Loads Gospels by category from JSON file."""
  with open(GOSPELS_BY_CATEGORY_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def generate_gospels_by_category_page():
  """Generates HTML for the Gospels by Category page."""
  categories = load_gospels_by_category()
  verse_refs = []
  for cat in categories:
    verse_ref = random.choice(cat["verses"])
    verse_refs.append(verse_ref)

  verse_texts = utils.fetch_passages(verse_refs)

  # Combine data for easier looping in Jinja2
  category_data = []
  for i, cat in enumerate(categories):
    category_data.append({
        "title": cat["title"],
        "description": cat["description"],
        "verses": cat["verses"],
        "prayer": cat["prayer"],
        "initial_verse_ref": verse_refs[i],
        "initial_verse_text": verse_texts[i],
    })

  print("Generated Gospels by Category HTML")
  return flask.render_template(
      "gospels_by_category.html", category_data=category_data
  )
