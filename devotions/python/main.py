"""Main Flask application for serving devotions."""

import datetime
import html
import os
import string
import advent
import close_of_day
import early_evening
import extended_evening
import flask
import morning
import noon
import prayer_requests
import pytz
import utils

app = flask.Flask(__name__)

INDEX_HTML_PATH = os.path.join(utils.SCRIPT_DIR, "..", "html", "index.html")
FEEDBACK_HTML_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "html", "feedback.html"
)
PRAYER_REQUESTS_HTML_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "html", "prayer_requests.html"
)
PRAYER_SUBMITTED_HTML_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "html", "prayer_request_submitted.html"
)
PRAYER_FAILED_HTML_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "html", "prayer_request_failed.html"
)
PRAYER_WALL_HTML_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "html", "prayer_wall.html"
)


@app.route("/")
def index_route():
  """Returns the homepage HTML."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  advent_button_html = ""
  if now.month == 12 and 1 <= now.day <= 25:
    advent_button_html = """<div class="card">
        <h2>Advent Devotion</h2>
        <a href="/advent_devotion" class="button">Advent Family Devotional</a>
    </div>"""

  with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
    template = string.Template(f.read())

  return template.substitute(advent_button_html=advent_button_html)


@app.route("/feedback")
def feedback_route():
  """Returns the feedback page HTML."""
  with open(FEEDBACK_HTML_PATH, "r", encoding="utf-8") as f:
    return f.read()


@app.route("/styles.css")
def styles():
  """Returns the styles.css file."""
  return flask.send_from_directory(
      os.path.join(utils.SCRIPT_DIR, "..", "html"), "styles.css"
  )


@app.route("/extended_evening_devotion")
def extended_evening_devotion_route():
  """Returns the generated devotion HTML."""
  return extended_evening.generate_extended_evening_devotion()


@app.route("/morning_devotion")
def morning_devotion_route():
  """Returns the generated devotion HTML."""
  return morning.generate_morning_devotion()


@app.route("/noon_devotion")
def noon_devotion_route():
  """Returns the generated devotion HTML."""
  return noon.generate_noon_devotion()


@app.route("/early_evening_devotion")
def early_evening_devotion_route():
  """Returns the generated devotion HTML."""
  return early_evening.generate_early_evening_devotion()


@app.route("/close_of_day_devotion")
def close_of_day_devotion_route():
  """Returns the generated devotion HTML."""
  return close_of_day.generate_close_of_day_devotion()


@app.route("/advent_devotion")
def advent_devotion_route():
  """Returns the generated devotion HTML."""
  return advent.generate_advent_devotion()


@app.route("/prayer_requests")
def prayer_requests_route():
  """Returns prayer request submission page."""
  with open(PRAYER_REQUESTS_HTML_PATH, "r", encoding="utf-8") as f:
    return f.read()


@app.route("/prayer_wall")
def prayer_wall_route():
  """Returns prayer wall page."""
  try:
    prayer_requests.remove_expired_requests()
  except Exception as e:
    print(f"Error removing expired prayer requests: {e}")
  requests = prayer_requests.get_prayer_wall_requests(limit=10)
  prayer_requests_html = ""
  if not requests:
    prayer_requests_html = (
        "<p><em>No active prayer requests at this time.</em></p>"
    )
  else:
    html_parts = []
    for i, req in enumerate(requests):
      name = html.escape(req.get("name", "Anonymous"))
      prayer = html.escape(req.get("request", ""))
      html_parts.append(f"<p><strong>{name}:</strong> {prayer}</p>")
      if i < len(requests) - 1:
        html_parts.append("<hr>")  # separator
    prayer_requests_html = "\n".join(html_parts)

  with open(PRAYER_WALL_HTML_PATH, "r", encoding="utf-8") as f:
    template = string.Template(f.read())
  return template.substitute(prayer_requests_html=prayer_requests_html)


@app.route("/add_prayer_request", methods=["POST"])
def add_prayer_request_route():
  """Adds a prayer request and returns confirmation or failure page."""
  name = flask.request.form.get("name")
  request = flask.request.form.get("request")
  days_ttl = flask.request.form.get("days_ttl", "30")
  if not name or not request:
    return flask.redirect("/prayer_requests")

  success, error_message = prayer_requests.add_prayer_request(
      name, request, days_ttl
  )
  if success:
    with open(PRAYER_SUBMITTED_HTML_PATH, "r", encoding="utf-8") as f:
      return f.read()
  else:
    with open(PRAYER_FAILED_HTML_PATH, "r", encoding="utf-8") as f:
      template = string.Template(f.read())
      return template.substitute(error_message=error_message)


if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
