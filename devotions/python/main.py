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
import psalms_by_category
import pytz
import utils

TEMPLATE_DIR = os.path.abspath(os.path.join(utils.SCRIPT_DIR, "..", "templates"))
STATIC_DIR = os.path.abspath(os.path.join(utils.SCRIPT_DIR, "..", "static"))
app = flask.Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR,
)

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
  is_advent = now.month == 12 and 1 <= now.day <= 25
  return flask.render_template("index.html", is_advent=is_advent)


@app.route("/feedback")
def feedback_route():
  """Returns the feedback page HTML."""
  return flask.render_template("feedback.html")


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
  return flask.render_template("prayer_requests.html")


@app.route("/get_passage_text")
def get_passage_text_route():
  """Fetches text for a given scripture reference."""
  ref = flask.request.args.get("ref")
  if not ref:
    return flask.jsonify({"error": "Missing reference"}), 400
  try:
    text = utils.fetch_passages([ref])[0]
    return flask.jsonify({"ref": ref, "text": text})
  except Exception as e:
    print(f"Error in get_passage_text: {e}")
    return flask.jsonify({"error": "Failed to fetch passage"}), 500


@app.route("/psalms_by_category")
def psalms_by_category_route():
  """Returns Psalms by Category page."""
  return psalms_by_category.generate_psalms_by_category_page()


@app.route("/prayer_wall")
def prayer_wall_route():
  """Returns prayer wall page."""
  try:
    prayer_requests.remove_expired_requests()
  except Exception as e:
    print(f"Error removing expired prayer requests: {e}")
  requests = prayer_requests.get_prayer_wall_requests(limit=10)
  if not requests:
    prayer_requests_html = (
        "<p><em>No active prayer requests at this time.</em></p>"
    )
  else:
    html_parts = []
    for req in requests:
      name = html.escape(req.get("name", "Anonymous"))
      prayer = html.escape(req.get("request", ""))
      html_parts.append(
          f'<li class="post-it"><p class="post-it-text">{prayer}</p><p'
          f' class="post-it-name">~ {name}</p></li>'
      )
    prayer_requests_html = (
        '<ul class="prayer-wall-container">\n'
        + "\n".join(html_parts)
        + "\n</ul>"
    )
  return flask.render_template(
      "prayer_wall.html", prayer_requests_html=prayer_requests_html
  )


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
    return flask.render_template("prayer_request_submitted.html")
  else:
    return flask.render_template(
        "prayer_request_failed.html", error_message=error_message
    )


if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
