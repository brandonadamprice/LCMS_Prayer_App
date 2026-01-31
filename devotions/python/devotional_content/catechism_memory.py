"""Functions for generating the Catechism Memorization page."""

from bs4 import BeautifulSoup
import flask
import utils


def strip_html(html_content):
  """Strips HTML tags to get clean text for memorization."""
  soup = BeautifulSoup(html_content, "html.parser")
  return soup.get_text().strip()


def generate_catechism_memory_page():
  """Generates HTML for the Catechism Memorization page."""
  catechism_data = utils.get_grouped_catechism()
  memorization_items = []

  # Flatten the grouped catechism into memorizable items
  for group_name, sections in catechism_data.items():
    # Memorize the entire catechism usually this refers to the Six Chief Parts.
    # But Table of Duties and Daily Prayers are often memorized too.
    # Christian Questions might be too long/many.
    # Let's include everything but structured well.

    for section in sections:
      # Main Text (e.g. The Commandment itself, or The Prayer)
      if section.get("text"):
        clean_text = strip_html(section["text"])
        if clean_text:
          memorization_items.append({
              "category": group_name,
              "title": f"{section['title']} (Text)",
              "text_html": section["text"],
              "clean_text": clean_text,
          })

      # Questions and Answers (Meanings)
      if section.get("questions_and_answers"):
        for qa in section["questions_and_answers"]:
          clean_answer = strip_html(qa["answer"])
          if clean_answer:
            title_suffix = qa["question"]
            if title_suffix == "What does this mean?":
              title_suffix = "Meaning"

            memorization_items.append({
                "category": group_name,
                "title": f"{section['title']} - {title_suffix}",
                "text_html": qa["answer"],
                "clean_text": clean_answer,
            })

  # Add indices for the frontend to usage
  for i, item in enumerate(memorization_items):
    item["id"] = i

  print("Generated Catechism Memorization HTML")
  return flask.render_template(
      "catechism_memory.html", items=memorization_items
  )
