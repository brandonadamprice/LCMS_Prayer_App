"""Main Flask application for serving devotions."""

import os
import flask
import extended_evening
import morning
import noon
import early_evening
import close_of_day
import advent
import utils
import datetime
import pytz
import string

app = flask.Flask(__name__)

INDEX_HTML_PATH = os.path.join(utils.SCRIPT_DIR, "..", "html", "index.html")
FEEDBACK_HTML_PATH = os.path.join(utils.SCRIPT_DIR, "..", "html", "feedback.html")


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


if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
