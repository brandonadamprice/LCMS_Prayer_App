"""Functions for generating the Trinity study page."""

import json
import os
import re
from functools import lru_cache

import flask
import utils

TRINITY_STUDY_JSON_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "trinity.json"
)


def _inject_references_in_text(text):
  """Finds scripture references in text and replaces them with tooltip spans."""
  if not text:
    return text
  # Pattern to find refs like: Gen 1:26, Deut 6:4, 1 John 5:7, 2 Cor 13:14
  pattern = re.compile(r"""\b((?:[1-3]\s)?[A-Za-z]+\s\d+:\d+(?:(?:–|-)\d+)?)\b""")
  matches = list(set(pattern.findall(text)))

  if not matches:
    return text

  try:
    texts = utils.fetch_passages(
        matches, include_verse_numbers=False, include_copyright=False
    )
    ref_map = {
        ref: txt
        for ref, txt in zip(matches, texts)
        if ref and "not available" not in txt and "ESV API" not in txt
    }

    sorted_refs = sorted(ref_map.keys(), key=len, reverse=True)
    for ref in sorted_refs:
      tooltip_text = ref_map[ref].replace('"', "&quot;").replace("\n", " ")
      replacement = (
          f'<span class="scripture-tooltip" data-text="{ref} &mdash;'
          f' {tooltip_text}">{ref}</span>'
      )
      try:
        # Use regex to replace only if it's a whole word match and not part of another ref
        text = re.sub(r"\b" + re.escape(ref) + r"\b", replacement, text)
      except re.error:
        # Fallback for safety
        text = text.replace(ref, replacement)
    return text
  except Exception as e:
    print(f"Error injecting references: {e}")
    return text


def _process_node(node):
  """Recursively processes nodes to inject tooltips into string values."""
  if isinstance(node, dict):
    return {k: _process_node(v) for k, v in node.items()}
  elif isinstance(node, list):
    return [_process_node(i) for i in node]
  elif isinstance(node, str):
    return _inject_references_in_text(node)
  else:
    return node


@lru_cache(maxsize=1)
def load_trinity_study_data():
  """Loads and processes Trinity study data from JSON file."""
  with open(TRINITY_STUDY_JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)
  return _process_node(data)


def generate_trinity_study_page():
  """Generates HTML for the Trinity study page."""
  study_data = load_trinity_study_data()
  template_data = study_data["study_of_the_holy_trinity"]
  print("Generated Trinity Study HTML")
  return flask.render_template("trinity_study.html", study=template_data)
