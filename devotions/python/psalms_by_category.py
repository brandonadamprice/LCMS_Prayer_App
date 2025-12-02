"""Functions for generating the Psalms by Category page."""

import json
import os
import random
import string
import utils

PSALMS_BY_CATEGORY_HTML_TEMPLATE_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "html", "psalms_by_category.html"
)
PSALMS_BY_CATEGORY_JSON_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "psalms_by_category.json"
)


def load_psalms_by_category():
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

  card_html_parts = []
  for i, cat in enumerate(categories):
    picker_buttons_html = "".join([
        f"""<button class="button psalm-picker-button" onclick="selectPsalm('{p}', {i})">{p}</button>"""
        for p in cat["Psalms"]
    ])
    card_html = f"""<div class="card collapsed">
            <div class="card-header" onclick="toggleCard(this)">
                <h2>{cat['title']}</h2>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="card-content">
                <p><em>{cat['description']}</em></p>
                <hr>
                <span class="ref" id="psalm-ref-{i}">{psalm_refs[i]}</span>
                <p id="psalm-text-{i}">{psalm_texts[i]}</p>
                <button class="button psalm-button" onclick="togglePsalmPicker(this, {i})">Select Psalm</button>
                <div id="picker-{i}" class="psalm-picker">
                    {picker_buttons_html}
                </div>
                <hr>
                <p class="subheader"><strong>Prayer</strong></p>
                <p>{cat['prayer']}</p>
            </div>
        </div>"""
    card_html_parts.append(card_html)

  all_cards_html = "\n".join(card_html_parts)

  with open(PSALMS_BY_CATEGORY_HTML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
    template = string.Template(f.read())

  html_content = template.substitute(category_cards_html=all_cards_html)
  print("Generated Psalms by Category HTML")
  return html_content
