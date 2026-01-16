"""Functions for generating the Small Catechism page."""

import flask
import utils


def get_grouped_catechism():
  """Groups the catechism sections into the Six Chief Parts."""
  sections = utils.CATECHISM_SECTIONS
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


def _inject_christian_questions_scripture(qa_list):
  """Prefetches and injects scripture text for specific questions."""
  # Question 4 (index 3)
  if 3 < len(qa_list) and "Romans 6:21" in qa_list[3]["answer"]:
    try:
      refs = ["Romans 6:21", "Romans 6:23"]
      texts = utils.fetch_passages(
          refs, include_verse_numbers=False, include_copyright=False
      )
      combined_text = (
          f"Rom 6:21: {texts[0]}\nRom 6:23: {texts[1]}"
      )
      # Escape for HTML attribute
      combined_text = combined_text.replace('"', "&quot;")
      qa_list[3]["answer"] = qa_list[3]["answer"].replace(
          "Romans 6:21,23",
          f'<span class="scripture-tooltip" data-text="{combined_text}">Romans 6:21,23</span>',
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
            f'<span class="scripture-tooltip" data-text="{tooltip_text}">{short_ref}</span>',
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
            f'<span class="scripture-tooltip" data-text="{content}">{label}</span>'
        )

      ans = qa_list[19]["answer"]

      # Simple replacements
      ans = ans.replace(
          "Galatians 5", mk_tooltip("Galatians 5", "Galatians 5:17")
      )
      ans = ans.replace("Romans 7", mk_tooltip("Romans 7", "Romans 7:18"))
      ans = ans.replace(
          "John 15-16", mk_tooltip("John 15-16", "John 15:18")
      )
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
