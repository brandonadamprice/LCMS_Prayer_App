"""Utility to scrape art from Full of Eyes."""

import functools
import logging
import random
import re
import time
import urllib.parse
import bs4
import requests

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=128)
def search_images_cached(query):
  """Cached wrapper for searching images."""
  scraper = FullOfEyesScraper()
  return scraper.search_images(query)


class FullOfEyesScraper:
  """Scraper for Full of Eyes website."""

  def __init__(self):
    self.base_url = "https://www.fullofeyes.com"
    self.gallery_url = "https://www.fullofeyes.com/gallery/"

    # Use a session to persist cookies across requests
    self.session = requests.Session()

    # mimick a real browser with a full set of headers
    self.headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Connection": "keep-alive",
    }

    # Update session headers
    self.session.headers.update(self.headers)

  def _get_soup(self, url):
    """Helper to fetch a URL and return a BeautifulSoup object."""
    try:
      # Randomize delay slightly to look more human
      time.sleep(random.uniform(1.0, 3.0))

      logger.info(f"Fetching: {url}")
      response = self.session.get(url, timeout=15)
      response.raise_for_status()

      # Log if redirect happened or just to confirm specific endpoint hit
      if response.url != url:
        logger.info(f"  -> Redirected to: {response.url}")

      return bs4.BeautifulSoup(response.content, "html.parser")
    except requests.exceptions.HTTPError as e:
      logger.error(f"HTTP Error fetching {url}: {e}")
      if e.response.status_code == 403:
        logger.warning(
            "Tip: A 403 error often means the site is blocking the script. Try"
            " waiting a few hours or changing your IP."
        )
      return None
    except requests.RequestException as e:
      logger.error(f"Error fetching {url}: {e}")
      return None

  def _get_next_page_url(self, soup):
    """Dynamically finds the 'Next' page URL from the pagination controls."""
    if not soup:
      return None

    # Common WordPress pagination classes and text
    next_link = soup.find("a", class_="next")

    if not next_link:
      # Fallback: Look for any link with "Next" text (case insensitive)
      next_link = soup.find("a", string=lambda t: t and "next" in t.lower())

    if not next_link:
      # Fallback: specific WordPress/theme pagination (e.g. numeric "2")
      pass

    if next_link and next_link.get("href"):
      return next_link["href"]

    return None

  def _parse_items_from_page(self, soup):
    """Parses image items from a gallery or search results page."""
    items = []
    if not soup:
      return items

    # Removed 'main' restriction.
    # Often the "Recent" or "Featured" images on Page 1 are in a header/hero section
    # outside the <main> tag. We search the body to capture everything.
    search_area = soup.find("body") or soup

    # Find all potential entry blocks.
    potential_items = search_area.find_all(["article", "div", "li"])

    unique_links = set()

    for el in potential_items:
      # Filter: Check if this element actually looks like a gallery item
      # 1. Must have an image
      img_tag = el.find("img")
      if not img_tag:
        continue

      # 2. Must have a title/link
      # We look for a header tag OR a link with reasonable text length
      title_tag = el.find(["h2", "h3", "h4", "h5"])
      link_tag = el.find("a", href=True)

      if not link_tag:
        # If the image itself isn't wrapped in a link and no title link, skip
        if el.name == "a":
          link_tag = el
        else:
          continue

      # --- Extraction ---

      # Link (Identifier)
      link = link_tag["href"]
      if link in unique_links:
        continue  # Skip duplicates

      # Title extraction
      if title_tag:
        title = title_tag.get_text(strip=True)
      elif link_tag.get_text(strip=True):
        title = link_tag.get_text(strip=True)
      else:
        title = "Untitled Image"

      # --- FILTERING ---

      # 1. Skip specific UI titles
      # This catches buttons like "Search All" that might wrap an image
      if title.lower() in [
          "search all",
          "search",
          "menu",
          "home",
          "submit",
          "advanced search",
      ]:
        continue

      # 2. Skip navigation/search links
      # Gallery items shouldn't point back to a search page
      if "/search/" in link or "?s=" in link:
        continue

      # Image URL extraction
      image_url = img_tag.get("data-src") or img_tag.get("src")
      if not image_url:
        continue

      image_url_lower = image_url.lower()

      # 3. Skip logos, avatars, spacers
      # Using lowercase to catch 'FOE-Logo' and 'logo'
      if "logo" in image_url_lower or "avatar" in image_url_lower:
        continue

      if "1x1" in image_url_lower or "spacer" in image_url_lower:
        continue

      # Success
      unique_links.add(link)
      items.append({"title": title, "image_url": image_url, "link": link})

    return items

  def fetch_recent_gallery_images(self, max_pages=1):
    """Fetches the most recent images from the main gallery.

    Args:
      max_pages: The maximum number of pages to fetch. Default is 1.

    Returns:
      A list of image dictionaries, each containing: "title", "image_url", and
      "link" properties.

    Follows 'Next' links dynamically.
    """
    all_items = []
    logger.info(f"Scraping up to {max_pages} pages from the main gallery...")

    # Start at the gallery URL
    current_url = self.gallery_url

    page_count = 0
    while current_url and page_count < max_pages:
      page_count += 1
      logger.info(f"--- Page {page_count} ---")

      soup = self._get_soup(current_url)
      if not soup:
        break

      items = self._parse_items_from_page(soup)
      if items:
        all_items.extend(items)
        logger.info(f"  Found {len(items)} items.")
      else:
        logger.info("  No items found on this page.")

      # Find the next page URL for the next iteration
      current_url = self._get_next_page_url(soup)
      if current_url:
        logger.info(f"  Next page found: {current_url}")
      else:
        logger.info("  No 'Next' page link found. Stopping.")
        break

    return all_items

  def search_images(self, query):
    """Searches for images using the website's specific search parameters.

    Args:
      query: The search query to perform.

    Returns:
      A list of image dictionaries, each containing: "title", "image_url", and
      "link" properties.

    Correct URL structure:
    /search/?_sf_s=QUERY&_sft_post_format=post-format-image
    """
    # Visit homepage first to ensure cookies are set
    if not self.session.cookies:
      self._get_soup(self.base_url)

    # Updated search URL structure
    encoded_query = urllib.parse.quote(query)
    search_url = f"{self.base_url}/search/?_sf_s={encoded_query}&_sft_post_format=post-format-image"

    logger.info(f"Searching for '{query}' at: {search_url}")

    soup = self._get_soup(search_url)
    results = self._parse_items_from_page(soup)

    # Basic verification: Ensure result has an image URL
    image_results = [item for item in results if item.get("image_url")]

    return image_results


def get_art_for_reading(reading_ref):
  """Searches for art based on a scripture reference."""
  if not reading_ref or reading_ref == "Reading not found":
    return None

  queries_to_try = []

  # 1. Base query: Book + Chapter (e.g., "Romans 4" from "Romans 4:1-25")
  if ":" in reading_ref:
    base_query = reading_ref.split(":")[0].strip()
    queries_to_try.append(base_query)

    # 2. Fallback: Book Name only (e.g., "Romans" from "Romans 4")
    # Remove the chapter number at the end
    book_match = re.match(r"^(.*?)\s+\d+$", base_query)
    if book_match:
      queries_to_try.append(book_match.group(1).strip())
  else:
    # Handle cases like "Jude 1-25" or "Obadiah 1" (no colon)
    # Try to capture "Jude 1" then "Jude"
    match = re.match(r"^(.*)\s+([\d\-]+)$", reading_ref)
    if match:
      book_name = match.group(1).strip()
      # If the second part contains digits, try Book + 1 as well as Book
      queries_to_try.append(f"{book_name} 1")
      queries_to_try.append(book_name)
    else:
      # Just try the whole thing if we can't parse it
      queries_to_try.append(reading_ref)

  # Remove duplicates while preserving order
  queries_to_try = list(dict.fromkeys(queries_to_try))

  logger.info(
      f"Searching art for ref '{reading_ref}' with queries: {queries_to_try}"
  )

  for query in queries_to_try:
    results = search_images_cached(query)
    if results:
      logger.info(f"Found art for query '{query}'")
      return results[0]

  logger.info("No art found.")
  return None


# Example Usage
# if __name__ == "__main__":
#   scraper = FullOfEyesScraper()
#
#   # 1. Fetch recent images
#   print("--- Fetching Recent Gallery Images ---")
#   recent_images = scraper.fetch_recent_gallery_images(max_pages=1)
#
#   if recent_images:
#     print(f"\nTotal fetched: {len(recent_images)}")
#     for i, img in enumerate(recent_images[:5]):
#       print(f"{i+1}. {img['title']} \n   Img: {img['image_url']}")
#   else:
#     print("No recent images found or access denied.")
#
#   print("\n" + "=" * 30 + "\n")
#
#   # 2. Search for images
#   search_term = "Cross"
#   print(f"--- Searching for '{search_term}' ---")
#   search_results = scraper.search_images(search_term)
#
#   if search_results:
#     for i, img in enumerate(search_results[:5]):
#       print(f"{i+1}. {img['title']} \n   Img: {img['image_url']}")
#   else:
#     print("No search results found.")
