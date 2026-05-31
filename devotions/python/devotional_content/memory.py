"""Functions for generating the Memory Verse page."""

import datetime
import json
import os
import re
from functools import lru_cache

import flask
import flask_login
import utils

MEMORY_VERSES_JSON_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "memory_verses.json"
)


@lru_cache(maxsize=1)
def load_predefined_verses():
  """Loads predefined memory verses from JSON file (cached; treat as read-only)."""
  with open(MEMORY_VERSES_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def get_user_verses(user_id):
  """Fetches user-added memory verses from Firestore."""
  db = utils.get_db_client()
  docs = (
      db.collection("user-memory-verses")
      .where("user_id", "==", user_id)
      .order_by("created_at")
      .stream()
  )
  verses = []
  for doc in docs:
    data = doc.to_dict()
    verses.append({
        "id": doc.id,
        "ref": data["ref"],
        "topic": data.get("topic", "User Added"),
    })
  return verses


def generate_memory_page():
  """Generates HTML for the Memory Verse page."""
  predefined_verses = load_predefined_verses()
  user_verses = []
  memorized_ids = []

  if flask_login.current_user.is_authenticated:
    user_verses = get_user_verses(flask_login.current_user.id)
    memorized_ids = flask_login.current_user.memorized_verses

  # Build metadata as fresh dicts so the cached predefined_verses list is
  # never mutated. Predefined verses get stable index-based IDs.
  all_verse_metadata = [
      {
          "id": f"predefined_{i}",
          "ref": v["ref"],
          "topic": v["topic"],
          "is_user": False,
      }
      for i, v in enumerate(predefined_verses)
  ] + [
      {
          "id": v["id"],
          "ref": v["ref"],
          "topic": v["topic"],
          "is_user": True,
      }
      for v in user_verses
  ]

  refs = list(
      dict.fromkeys([v["ref"] for v in all_verse_metadata])
  )  # unique refs

  try:
    texts_html = utils.fetch_passages(
        refs, include_verse_numbers=True, include_copyright=True
    )
    clean_texts = utils.fetch_passages(
        refs, include_verse_numbers=False, include_copyright=False
    )
  except Exception as e:
    return flask.render_template(
        "prayer_request_failed.html",
        error_message=f"Failed to fetch verse texts: {e}",
    )

  ref_to_text_map = dict(zip(refs, zip(texts_html, clean_texts)))

  verses_for_template = []
  for v in all_verse_metadata:
    html, clean = ref_to_text_map.get(v["ref"], ("Not found", "Not found"))
    clean_text_single_line = re.sub(r"\s+", " ", clean).strip()
    verse_item = {
        "id": v["id"],
        "ref": v["ref"],
        "topic": v["topic"],
        "text_html": html,
        "clean_text": clean_text_single_line,
        "is_user": v["is_user"],
        "is_memorized": v["id"] in memorized_ids,
    }
    verses_for_template.append(verse_item)

  template_data = {"verses": verses_for_template}
  return flask.render_template("memory.html", **template_data)
