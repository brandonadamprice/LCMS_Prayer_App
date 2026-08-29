"""Data-integrity tests for devotions/data/mary.json.

The Mary study page (`/mary_study`) renders straight from this file, and the
template skips anything it cannot find: a mistyped key ("scripture" for
"scriptures") drops the references silently, and a malformed <bible-ref> tag
survives into the page as literal markup because
utils.inject_references_in_text only rewrites balanced pairs. Both fail
quietly in a browser, so they are checked here instead.

The suite is pure JSON + stdlib -- no flask, no google-cloud imports. Run
from the repo root:

    python -m unittest discover -s devotions/python/tests -t devotions/python
"""

import json
import os
import re
import unittest

MARY_JSON_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "mary.json"
)

# Books this study draws on, longest-first so "1 John" is not read as "John"
# and "1 Timothy" is not truncated.
BOOK_NAMES = sorted(
    (
        "Psalm", "Isaiah", "Matthew", "Luke", "John", "Romans", "Galatians",
        "1 Timothy", "Hebrews", "1 Peter", "1 John",
    ),
    key=len,
    reverse=True,
)

# "Luke 1:38" or "Luke 1:31-35" -- what the ESV API can resolve.
_REFERENCE = re.compile(r"\d+:\d+(-\d+)?$")

_BIBLE_REF_TAG = re.compile(r"<bible-ref>(.*?)</bible-ref>", re.DOTALL)


def load():
  with open(MARY_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)["mary_study"]


def walk_strings(node):
  """Yields every string value in the tree."""
  if isinstance(node, dict):
    for value in node.values():
      yield from walk_strings(value)
  elif isinstance(node, list):
    for value in node:
      yield from walk_strings(value)
  elif isinstance(node, str):
    yield node


class StructureTests(unittest.TestCase):
  """The shape the template reads."""

  def setUp(self):
    self.study = load()

  def test_top_level_keys(self):
    for key in ("title", "category", "description", "sections",
                "confessional_summary"):
      self.assertIn(key, self.study)

  def test_sections_carry_heading_summary_and_items(self):
    self.assertTrue(self.study["sections"])
    for section in self.study["sections"]:
      for key in ("id", "heading", "summary", "items"):
        self.assertIn(key, section, f"{section.get('heading')} missing {key}")
        self.assertTrue(section[key], f"{section.get('heading')}: {key} is empty")

  def test_section_ids_are_unique_url_fragments(self):
    ids = [section["id"] for section in self.study["sections"]]
    self.assertEqual(len(ids), len(set(ids)))
    for section_id in ids:
      self.assertRegex(section_id, r"^[a-z0-9]+(-[a-z0-9]+)*$")

  def test_every_item_has_a_title_and_a_body(self):
    for section in self.study["sections"]:
      for item in section["items"]:
        self.assertTrue(item.get("title"), f"{section['id']}: item has no title")
        # An item renders either as prose (description) or as a quoted text
        # with the Lutheran reading of it. One or the other must be present,
        # or the item renders as a bare heading.
        self.assertTrue(
            item.get("description") or item.get("text"),
            f"{section['id']}/{item['title']} has no body",
        )
        if item.get("text"):
          self.assertTrue(
              item.get("lutheran_view"),
              f"{section['id']}/{item['title']} quotes a text with no"
              " Lutheran reading of it",
          )

  def test_item_keys_are_ones_the_template_renders(self):
    # Guards the silent-drop case: a key the template never looks up.
    allowed = {
        "title", "description", "text", "lutheran_view", "scriptures",
        "confessional_references",
    }
    for section in self.study["sections"]:
      for item in section["items"]:
        unknown = set(item) - allowed
        self.assertFalse(
            unknown, f"{section['id']}/{item['title']}: unrendered keys {unknown}"
        )

  def test_confessional_summary_has_both_columns(self):
    summary = self.study["confessional_summary"]
    for key in ("we_confess", "we_reject"):
      self.assertIn(key, summary)
      self.assertTrue(summary[key])
      for line in summary[key]:
        self.assertTrue(line.strip())


class ScriptureReferenceTests(unittest.TestCase):
  """Every <bible-ref> must be one the ESV API can resolve."""

  def setUp(self):
    self.study = load()

  def test_bible_ref_tags_are_balanced(self):
    # inject_references_in_text rewrites only balanced pairs; a stray opening
    # tag would be printed to the page verbatim.
    for text in walk_strings(self.study):
      self.assertEqual(
          text.count("<bible-ref>"),
          text.count("</bible-ref>"),
          f"unbalanced <bible-ref> in: {text[:60]}",
      )

  def test_tagged_references_name_a_real_book_and_verse(self):
    refs = [
        ref
        for text in walk_strings(self.study)
        for ref in _BIBLE_REF_TAG.findall(text)
    ]
    self.assertTrue(refs, "the study cites no scripture")
    for ref in refs:
      book = next(
          (b for b in BOOK_NAMES if ref.startswith(b + " ")), None
      )
      self.assertIsNotNone(book, f"unrecognized book in {ref!r}")
      self.assertRegex(ref[len(book) + 1:], _REFERENCE, f"bad reference {ref!r}")

  def test_reference_ranges_do_not_run_backwards(self):
    for text in walk_strings(self.study):
      for ref in _BIBLE_REF_TAG.findall(text):
        match = re.search(r":(\d+)-(\d+)$", ref)
        if match:
          self.assertLess(
              int(match.group(1)), int(match.group(2)), f"backwards range {ref!r}"
          )

  def test_every_scripture_entry_is_a_tagged_reference(self):
    # A bare "Luke 1:38" renders as plain text with no tooltip.
    for section in self.study["sections"]:
      for item in section["items"]:
        for ref in item.get("scriptures", []):
          self.assertRegex(
              ref,
              r"^<bible-ref>.+</bible-ref>$",
              f"{section['id']}/{item['title']}: untagged reference {ref!r}",
          )


if __name__ == "__main__":
  unittest.main()
