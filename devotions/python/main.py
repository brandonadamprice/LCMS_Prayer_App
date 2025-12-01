"""Main Flask application for serving devotions."""

import os
import flask
import extended_evening
import morning
import utils

app = flask.Flask(__name__)

INDEX_HTML_PATH = os.path.join(utils.SCRIPT_DIR, "..", "html", "index.html")


@app.route("/")
def index_route():
  """Returns the homepage HTML."""
  with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
    return f.read()


@app.route("/styles.css")
def styles():
  """Returns the styles.css file."""
  return flask.send_from_directory(
      os.path.join(utils.SCRIPT_DIR, "..", "html"), "styles.css"
  )


@app.route("/extended_evening_devotion")
def evening_devotion_route():
  """Returns the generated devotion HTML."""
  return extended_evening.generate_evening_devotion()


@app.route("/morning_devotion")
def morning_devotion_route():
  """Returns the generated devotion HTML."""
  return morning.generate_morning_devotion()


if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
