"""Service for interacting with the ESV API."""

import functools
import re
import requests
import secrets_fetcher as secrets


def _preprocess_ref(ref: str) -> str:
  """Expands shorthand Bible references with semicolons and commas.

  Example: '1 Cor 7:17;23-24' becomes '1 Cor 7:17;1 Cor 7:23-24'.
  'Gen 27:30-45; 28:10-22' becomes 'Gen 27:30-45;Gen 28:10-22'.
  '2 John 1-13; 3 John 1-15' remains '2 John 1-13;3 John 1-15'.
  Handles verses only, or chapter:verses after semicolon.
  """
  splitting_delimiters = [";", ","]
  delim = ""
  for splitting_delimiter in splitting_delimiters:
    if splitting_delimiter in ref:
      delim = splitting_delimiter
      break
  if not delim:
    return ref

  parts = ref.split(delim)
  first_part = parts[0].strip()
  book_chapter_if_present = ""

  colon_idx = first_part.rfind(":")
  if colon_idx > -1:
    # multi-chapter book reference format, e.g. "Genesis 1:1"
    book_chapter_if_present = first_part[:colon_idx].strip()
    # regex to capture book name and chapter number
    book_match = re.match(r"(.*\D)\s*(\d+)$", book_chapter_if_present)
    if book_match:
      book = book_match.group(1).strip()
    else:
      book = ""
  else:
    # single-chapter book reference format, like "Jude 1-4" or "2 John 10"
    first_digit_match = re.search(r"\d", first_part)
    if first_digit_match:
      book = first_part[: first_digit_match.start()].strip()
    else:
      book = ""

  if not book:
    return ref

  processed_parts = [first_part]
  for part in parts[1:]:
    part = part.strip()
    # Remove f/ff suffixes for API query
    clean_part = re.sub(r"ff?$", "", part).strip()
    if re.fullmatch(r"\d+(-\d+)?", clean_part):  # verses only
      if book_chapter_if_present:
        processed_parts.append(f"{book_chapter_if_present}:{clean_part}")
      else:  # single chapter book
        processed_parts.append(f"{book} {clean_part}")
    elif re.fullmatch(r"\d+:\d+(-\d+)?", clean_part):  # chapter:verses
      processed_parts.append(f"{book} {clean_part}")
    else:
      processed_parts.append(clean_part)
  return ";".join(processed_parts)


@functools.lru_cache(maxsize=512)
def _fetch_passages_cached(
    references: tuple[str, ...],
    include_verse_numbers: bool = True,
    include_copyright: bool = True,
) -> tuple[str, ...]:
  """Cached fetching of passages from api.esv.org."""
  passage_results = {}
  references_list = list(references)

  # original_ref -> list of preprocessed refs for ESV
  ref_map = {}
  esv_query_parts = []

  for ref in references_list:
    if ref and ref != "Daily Lectionary Not Found":
      preref = _preprocess_ref(ref)
      ref_map[ref] = preref.split(";")
      esv_query_parts.append(preref)
      passage_results[ref] = "<i>Reading not available.</i>"
    else:
      passage_results[ref] = "<i>Reading not available.</i>"

  if not esv_query_parts:
    return tuple(passage_results[ref] for ref in references_list)

  api_key = secrets.get_esv_api_key()
  if not api_key:
    for ref in ref_map:
      passage_results[ref] = (
          "<i>ESV_API_KEY environment variable not set. Cannot fetch text.</i>"
      )
    return tuple(passage_results[ref] for ref in references_list)

  query = ";".join(esv_query_parts)
  params = {
      "q": query,
      "include-headings": "false",
      "include-footnotes": "false",
      "include-verse-numbers": str(include_verse_numbers).lower(),
      "include-passage-references": "false",
      "include-chapter-numbers": "false",
      "include-copyright": str(include_copyright).lower(),
  }
  headers = {"Authorization": f"Token {api_key}"}

  try:
    response = requests.get(
        "https://api.esv.org/v3/passage/text/",
        params=params,
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("passages"):
      passage_idx = 0
      for ref in references_list:
        if ref in ref_map:
          num_passages = len(ref_map[ref])
          if passage_idx + num_passages <= len(data["passages"]):
            passages_list = data["passages"][
                passage_idx : passage_idx + num_passages
            ]
            if passages_list:
              if len(passages_list) > 1 and include_copyright:
                processed_passages = [
                    p.strip().removesuffix(" (ESV)") for p in passages_list[:-1]
                ]
                processed_passages.append(passages_list[-1].strip())
                text_block = " ".join(processed_passages)
              else:
                text_block = " ".join(p.strip() for p in passages_list)

              if include_copyright and text_block.endswith(" (ESV)"):
                text_block = (
                    text_block.removesuffix(" (ESV)")
                    + ' <span class="esv-attribution">(<a'
                    ' href="http://www.esv.org">ESV</a>)</span>'
                )
              elif not include_copyright and text_block.endswith(" (ESV)"):
                text_block = text_block.removesuffix(" (ESV)")
            else:
              text_block = ""

            if include_verse_numbers:
              text_block = re.sub(
                  r"\[(\d+)\]", r"<br><sup>\1</sup>", text_block
              )
              if text_block.startswith("<br>"):
                text_block = text_block[4:]
            else:
              text_block = re.sub(r"\[\d+\]", "", text_block).strip()

            passage_results[ref] = text_block
            passage_idx += num_passages
          else:
            passage_results[ref] = f"<i>(Text not found for {ref})</i>"
        # If ref not in ref_map, it's already "Reading not available"
    else:
      for ref in ref_map:
        passage_results[ref] = f"<i>(Text not found for {ref})</i>"

    return tuple(passage_results[ref] for ref in references_list)

  except requests.exceptions.RequestException as e:
    print(f"Error fetching from ESV API: {e}")
    error_msg = "<i>(Could not connect to ESV API)</i>"
    for ref in ref_map:
      passage_results[ref] = error_msg
    return tuple(passage_results[ref] for ref in references_list)
  except Exception as e:
    print(f"Error processing ESV API response: {e}")
    error_msg = "<i>(Error processing ESV API response)</i>"
    for ref in ref_map:
      passage_results[ref] = error_msg
    return tuple(passage_results[ref] for ref in references_list)


def fetch_passages(
    references: list[str],
    include_verse_numbers: bool = True,
    include_copyright: bool = True,
) -> list[str]:
  """Fetches multiple passages from api.esv.org in one request."""
  return list(
      _fetch_passages_cached(
          tuple(references), include_verse_numbers, include_copyright
      )
  )
