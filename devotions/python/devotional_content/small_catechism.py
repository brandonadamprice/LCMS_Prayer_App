"""Functions for generating the Small Catechism page."""

import json
import os
import re
import flask
import utils

CATECHISM_EXPLANATION_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "data", "catechism_explaination.json"
)


def load_catechism_explanation():
  """Loads the catechism explanation data."""
  try:
    with open(CATECHISM_EXPLANATION_PATH, "r", encoding="utf-8") as f:
      return json.load(f)
  except FileNotFoundError:
    print(f"Warning: {CATECHISM_EXPLANATION_PATH} not found.")
    return {}


def get_grouped_catechism():
  """Groups the catechism sections into the Six Chief Parts."""
  sections = utils.CATECHISM_SECTIONS
  explanation_data = load_catechism_explanation()

  # Create a lookup for explanations by title
  explanations_map = {}

  # List of keys in explanation_data that contain lists of items with "title"
  keys_to_load = [
      "ten_commandments",
      "apostles_creed",
      "lords_prayer",
      "sacrament_of_holy_baptism",
      "confession_and_office_of_the_keys",
      "sacrament_of_the_altar",
      "daily_prayers",
  ]

  for key in keys_to_load:
    if key in explanation_data:
      for item in explanation_data[key]:
        if "title" in item:
          explanations_map[item["title"]] = item

  groups = {
      "The Ten Commandments": [],
      "The Apostles' Creed": [],
      "The Lord's Prayer": [],
      "The Sacrament of Holy Baptism": [],
      "Confession": [],
      "The Sacrament of the Altar": [],
      "Daily Prayers": [],
      "Table of Duties": [],
      "Christian Questions with Their Answers": [],
  }

  for section in sections:
    title = section["title"]

    # Inject explanation data if available
    if title in explanations_map:
      explanation_text = explanations_map[title]["explanation"]
      # Replace markdown bold **text** with <strong>text</strong>
      explanation_text = re.sub(
          r"\*\*(.*?)\*\*", r"<strong>\1</strong>", explanation_text
      )
      # Inject tooltips for explanation text
      explanation_text = inject_references(explanation_text)
      
      section["explanation"] = explanation_text
      section["quiz_questions"] = explanations_map[title]["questions"]
    
    # Inject tooltips for main section text if present (e.g. Table of Duties)
    if "text" in section and section["text"]:
      section["text"] = inject_references(section["text"])

    if "Commandment" in title or "Close of the Commandments" in title:
      groups["The Ten Commandments"].append(section)
    elif "Creed" in title:
      groups["The Apostles' Creed"].append(section)
    elif "Lord's Prayer" in title:
      groups["The Lord's Prayer"].append(section)
    elif "Baptism" in title:
      groups["The Sacrament of Holy Baptism"].append(section)
    elif "Confession" in title or "Office of the Keys" in title:
      groups["Confession"].append(section)
    elif "Sacrament of the Altar" in title:
      groups["The Sacrament of the Altar"].append(section)
    elif title in [
        "Morning Prayer",
        "Evening Prayer",
        "Asking a Blessing",
        "Returning Thanks",
    ]:
      groups["Daily Prayers"].append(section)
    elif "Table of Duties" in title:
      groups["Table of Duties"].append(section)
    elif "Christian Questions" in title:
      # Inject scripture texts for Christian Questions if not already present
      if "questions_and_answers" in section:
        _inject_christian_questions_scripture(section["questions_and_answers"])
      groups["Christian Questions with Their Answers"].append(section)
    else:
      # Fallback for any unmatched sections
      if "Other" not in groups:
        groups["Other"] = []
      groups["Other"].append(section)

  # Filter out empty groups and return
  return {k: v for k, v in groups.items() if v}


def inject_references(text):
  """Injects scripture tooltips into text."""
  if not text:
    return text

  # Pattern: (Book) (Chapter):(Verse)(Optional Range)(Optional Suffix)
  # Matches: 1 Tim. 3:2, Rom. 13:1-4, John 20:22–23 (en-dash), Titus 3:5
  # Does NOT match: "John 14" (chapter only) unless we expand regex, but user only asked for what we see.
  # "Christian Questions" uses "John 14; Romans 5".
  # "Table of Duties" uses "1 Tim. 3:2ff".
  # "Explanation" uses "Matthew 28:19", "Romans 6:4".
  
  # Refined Pattern:
  # 1. Optional Prefix: 1, 2, 3, I, II, III
  # 2. Book Name: [A-Z][a-z]+ (one or more words allowed? e.g. Song of Solomon? Usually single word + prefix in these contexts)
  # 3. Separator
  # 4. Chapter:Verse
  # 5. Optional range/suffix

  # Note: This simple regex handles standard single-word books or numbered books. 
  # Complex books like "Song of Solomon" might need more work if present.
  pattern = r'\b((?:1|2|3|I|II|III)?\s*[A-Z][a-z]+\.?\s+\d+:\d+(?:[-–]\d+)?(?:ff|f)?)'
  
  matches = list(set(re.findall(pattern, text)))
  if not matches:
    return text

  # Clean refs for API
  clean_refs = []
  for m in matches:
    clean = m.replace('–', '-').replace('ff', '').replace('f', '').strip()
    clean_refs.append(clean)
  
  try:
    texts = utils.fetch_passages(clean_refs, include_verse_numbers=False, include_copyright=False)
    ref_map = dict(zip(matches, texts))
    
    for ref_str, scripture_text in ref_map.items():
      # Skip if reading not available
      if "Reading not available" in scripture_text:
        continue
      
      # Basic HTML escaping for attribute
      escaped_text = scripture_text.replace('"', '&quot;')
      tooltip = f'<span class="scripture-tooltip" data-text="{escaped_text}">{ref_str}</span>'
      
      # Replace in text. Use string replace.
      text = text.replace(ref_str, tooltip)
      
  except Exception as e:
    print(f"Error injecting references: {e}")
    
  return text


def _inject_christian_questions_scripture(qa_list):
  """Prefetches and injects scripture text for specific questions."""
  # Question 4 (index 3)
  if 3 < len(qa_list) and "Romans 6:21" in qa_list[3]["answer"]:
    try:
      refs = ["Romans 6:21", "Romans 6:23"]
      texts = utils.fetch_passages(
          refs, include_verse_numbers=False, include_copyright=False
      )
      combined_text = f"Rom 6:21: {texts[0]}\nRom 6:23: {texts[1]}"
      # Escape for HTML attribute
      combined_text = combined_text.replace('"', "&quot;")
      qa_list[3]["answer"] = qa_list[3]["answer"].replace(
          "Romans 6:21,23",
          f'<span class="scripture-tooltip" data-text="{combined_text}">Romans'
          " 6:21,23</span>",
      )
    except Exception as e:
      print(f"Error injecting scripture for Q4: {e}")

  # Question 17 (index 16)
  if 16 < len(qa_list) and "John 14" in qa_list[16]["answer"]:
    try:
      # Key verses to display in tooltip
      ref_map = {
          "John 14": "John 14:6",
          "Romans 5": "Romans 5:8",
          "Galatians 2": "Galatians 2:20",
          "Ephesians 5": "Ephesians 5:2",
      }
      # Fetch all at once to minimize requests
      refs_to_fetch = list(ref_map.values())
      texts = utils.fetch_passages(
          refs_to_fetch, include_verse_numbers=False, include_copyright=False
      )
      # Map back ref_key -> text
      text_map = dict(zip(refs_to_fetch, texts))

      for short_ref, full_ref in ref_map.items():
        verse_text = text_map.get(full_ref, "")
        tooltip_text = f"{full_ref}: {verse_text}".replace('"', "&quot;")
        qa_list[16]["answer"] = qa_list[16]["answer"].replace(
            short_ref,
            '<span class="scripture-tooltip"'
            f' data-text="{tooltip_text}">{short_ref}</span>',
        )
    except Exception as e:
      print(f"Error injecting scripture for Q17: {e}")

  # Question 20 (index 19)
  if 19 < len(qa_list) and "Galatians 5" in qa_list[19]["answer"]:
    try:
      # Define mappings for Q20 refs
      refs_to_fetch = [
          "Galatians 5:17",
          "Romans 7:18",
          "John 15:18",  # Representative verse for John 15-16
          "1 John 2:15-16",
          "1 John 5:19",
          "John 8:44",
          "John 16:11",
          "1 Peter 5:8",
          "Ephesians 6:11",
          "2 Timothy 2:26",
      ]
      texts = utils.fetch_passages(
          refs_to_fetch, include_verse_numbers=False, include_copyright=False
      )
      text_map = dict(zip(refs_to_fetch, texts))

      def mk_tooltip(label, ref_key):
        content = f"{ref_key}: {text_map.get(ref_key, '')}".replace(
            '"', "&quot;"
        )
        return (
            '<span class="scripture-tooltip"'
            f' data-text="{content}">{label}</span>'
        )

      ans = qa_list[19]["answer"]

      # Simple replacements
      ans = ans.replace(
          "Galatians 5", mk_tooltip("Galatians 5", "Galatians 5:17")
      )
      ans = ans.replace("Romans 7", mk_tooltip("Romans 7", "Romans 7:18"))
      ans = ans.replace("John 15-16", mk_tooltip("John 15-16", "John 15:18"))
      ans = ans.replace("1 Peter 5", mk_tooltip("1 Peter 5", "1 Peter 5:8"))
      ans = ans.replace(
          "Ephesians 6", mk_tooltip("Ephesians 6", "Ephesians 6:11")
      )
      ans = ans.replace(
          "2 Timothy 2", mk_tooltip("2 Timothy 2", "2 Timothy 2:26")
      )

      # Composite replacements
      ans = ans.replace(
          "1 John 2 and 5",
          f"{mk_tooltip('1 John 2', '1 John 2:15-16')} and"
          f" {mk_tooltip('5', '1 John 5:19')}",
      )
      ans = ans.replace(
          "John 8 and 16",
          f"{mk_tooltip('John 8', 'John 8:44')} and"
          f" {mk_tooltip('16', 'John 16:11')}",
      )

      qa_list[19]["answer"] = ans

    except Exception as e:
      print(f"Error injecting scripture for Q20: {e}")


def generate_small_catechism_page():
  """Generates HTML for the Small Catechism page."""
  grouped_catechism = get_grouped_catechism()

  print("Generated Small Catechism HTML")
  return flask.render_template(
      "small_catechism.html",
      grouped_catechism=grouped_catechism,
  )
