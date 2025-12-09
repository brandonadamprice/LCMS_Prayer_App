"""Main Flask application for serving devotions."""

import datetime
import hashlib
import html
import os
import secrets
import advent
from authlib.integrations.flask_client import OAuth
import bible_in_a_year
import childrens_devotion
import close_of_day
import evening
import extended_evening
import flask
import flask_login
from google.cloud import firestore
from google.cloud.firestore_v1 import base_query
from google.cloud.firestore_v1.field_path import FieldPath
import gospels_by_category
import mid_week
import midday
import morning
import night_watch
import one_hundred_prayers
import prayer_requests
import psalms_by_category
import pytz
import secrets_fetcher
import utils


TEMPLATE_DIR = os.path.abspath(
    os.path.join(utils.SCRIPT_DIR, "..", "templates")
)
STATIC_DIR = os.path.abspath(os.path.join(utils.SCRIPT_DIR, "..", "static"))
app = flask.Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR,
)
app.secret_key = secrets_fetcher.get_flask_secret_key()
app.config["OTHER_PRAYERS"] = utils.get_other_prayers()
try:
  app.config["ADMIN_USER_ID"] = secrets_fetcher.get_brandon_user_id()
except:
  app.config["ADMIN_USER_ID"] = None

# OAuth and Flask-Login Setup
oauth = OAuth(app)
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

google = oauth.register(
    name="google",
    client_id=secrets_fetcher.get_google_client_id(),
    client_secret=secrets_fetcher.get_google_client_secret(),
    server_metadata_url=(
        "https://accounts.google.com/.well-known/openid-configuration"
    ),
    client_kwargs={"scope": "openid email profile"},
)


class User(flask_login.UserMixin):
  """User class for Flask-Login."""

  def __init__(
      self,
      user_id,
      email=None,
      name=None,
      profile_pic=None,
      dark_mode=None,
      font_size_level=None,
  ):
    self.id = user_id
    self.email = email
    self.name = name
    self.profile_pic = profile_pic
    self.dark_mode = dark_mode
    self.font_size_level = font_size_level

  @staticmethod
  def get(user_id):
    """Gets a user from Firestore by user_id (which is Google's sub)."""
    db = utils.get_db_client()
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    if user_doc.exists:
      data = user_doc.to_dict()
      return User(
          user_id=user_id,
          email=data.get("email"),
          name=data.get("name"),
          profile_pic=data.get("profile_pic"),
          dark_mode=data.get("dark_mode"),
          font_size_level=data.get("font_size_level"),
      )
    return None


@login_manager.user_loader
def load_user(user_id):
  """Flask-Login user loader."""
  return User.get(user_id)


def create_or_update_google_user(user_info):
  """Creates or updates a user in Firestore based on Google profile info."""
  db = utils.get_db_client()
  user_id = user_info["sub"]
  user_ref = db.collection("users").document(user_id)
  user_ref.set(
      {
          "google_id": user_id,
          "email": user_info.get("email"),
          "name": user_info.get("name"),
          "profile_pic": user_info.get("picture"),
          "last_login": datetime.datetime.now(datetime.timezone.utc),
      },
      merge=True,
  )
  return User.get(user_id)


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
  return flask.render_template(
      "index.html",
      is_advent=is_advent,
      admin_user_id=app.config.get("ADMIN_USER_ID"),
  )


@app.route("/feedback")
def feedback_route():
  """Returns the feedback page HTML."""
  return flask.render_template("feedback.html")


@app.route("/about")
def about_route():
  """Returns the about page HTML."""
  return flask.render_template("about.html")


@app.route("/copyright")
def copyright_route():
  """Returns the copyright page HTML."""
  return flask.render_template("copyright.html")


@app.route("/login")
def login():
  """Redirects to Google OAuth login."""
  redirect_uri = flask.url_for("authorize", _external=True)
  nonce = secrets.token_urlsafe()
  flask.session["nonce"] = nonce
  return google.authorize_redirect(redirect_uri, nonce=nonce)


@app.route("/authorize")
def authorize():
  """Callback route for Google OAuth."""
  try:
    token = google.authorize_access_token()
    nonce = flask.session.pop("nonce", None)
    user_info = google.parse_id_token(token, nonce=nonce)
    user = create_or_update_google_user(user_info)
    flask_login.login_user(user)
    return flask.redirect("/")
  except Exception as e:
    app.logger.warning("OAuth Error: %s", e)
    return "Authentication failed.", 400


@app.route("/logout")
@flask_login.login_required
def logout():
  """Logs out the current user."""
  flask_login.logout_user()
  return flask.redirect("/")


@app.route("/extended_evening_devotion")
def extended_evening_devotion_route():
  """Returns the generated devotion HTML."""
  return extended_evening.generate_extended_evening_devotion()


@app.route("/morning_devotion")
def morning_devotion_route():
  """Returns the generated devotion HTML."""
  return morning.generate_morning_devotion()


@app.route("/midday_devotion")
def midday_devotion_route():
  """Returns the generated devotion HTML."""
  return midday.generate_midday_devotion()


@app.route("/evening_devotion")
def evening_devotion_route():
  """Returns the generated devotion HTML."""
  return evening.generate_evening_devotion()


@app.route("/close_of_day_devotion")
def close_of_day_devotion_route():
  """Returns the generated devotion HTML."""
  return close_of_day.generate_close_of_day_devotion()


@app.route("/mid_week_devotion")
def mid_week_devotion_route():
  """Returns the generated mid-week devotion HTML."""
  return mid_week.generate_mid_week_devotion()


@app.route("/advent_devotion")
def advent_devotion_route():
  """Returns the generated devotion HTML."""
  return advent.generate_advent_devotion()


@app.route("/childrens_devotion")
def childrens_devotion_route():
  """Returns the generated children's devotion HTML."""
  return childrens_devotion.generate_childrens_devotion()


@app.route("/night_watch_devotion")
def night_watch_devotion_route():
  """Returns the generated devotion HTML."""
  return night_watch.generate_night_watch_devotion()


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


@app.route("/gospels_by_category")
def gospels_by_category_route():
  """Returns Gospels by Category page."""
  return gospels_by_category.generate_gospels_by_category_page()


@app.route("/100_prayers")
def one_hundred_prayers_route():
  """Returns 100 Prayers page."""
  return one_hundred_prayers.generate_100_prayers_page()


@app.route("/bible_in_a_year")
def bible_in_a_year_route():
  """Returns Bible in a Year page."""
  bia_progress = None
  if flask_login.current_user.is_authenticated:
    db = utils.get_db_client()
    doc = db.collection("users").document(flask_login.current_user.id).get()
    if doc.exists:
      bia_progress = doc.to_dict().get("bia_progress")
  return bible_in_a_year.generate_bible_in_a_year_page(bia_progress)


@app.route("/save_bia_progress", methods=["POST"])
@flask_login.login_required
def save_bia_progress_route():
  """Saves Bible in a Year progress for the current user."""
  data = flask.request.json
  day = data.get("day")
  last_visit = data.get("last_visit")
  if isinstance(day, int) and last_visit:
    try:
      bible_in_a_year.save_bia_progress(
          flask_login.current_user.id, day, last_visit
      )
      return flask.jsonify({"success": True})
    except Exception as e:
      app.logger.error("Failed to save BIA progress: %s", e)
      return (
          flask.jsonify({"success": False, "error": "Database save failed"}),
          500,
      )
  return (
      flask.jsonify({"success": False, "error": "Invalid progress data"}),
      400,
  )


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
    prayed_request_ids = []
    if flask_login.current_user.is_authenticated:
      db = utils.get_db_client()
      user_doc_ref = db.collection("users").document(
          flask_login.current_user.id
      )
      user_doc = user_doc_ref.get()
      if user_doc.exists:
        prayed_request_ids = user_doc.to_dict().get("prayed_request_ids", [])
        if prayed_request_ids:
          active_prayed_request_ids = []
          prayer_requests_ref = db.collection("prayer-requests")
          for request_id in prayed_request_ids:
            prayer_request_doc = prayer_requests_ref.document(request_id).get()
            if prayer_request_doc.exists:
              active_prayed_request_ids.append(request_id)

          if len(active_prayed_request_ids) < len(prayed_request_ids):
            user_doc_ref.update(
                {"prayed_request_ids": active_prayed_request_ids}
            )
            prayed_request_ids = active_prayed_request_ids
    html_parts = []
    for req in requests:
      name = html.escape(req.get("name", "Anonymous"))
      prayer = html.escape(req.get("request", ""))
      req_id = req.get("id", "")
      pray_count = req.get("pray_count", 0)
      prayed_class = "prayed" if req_id in prayed_request_ids else ""
      is_owner = (
          flask_login.current_user.is_authenticated
          and req.get("user_id") == flask_login.current_user.id
      )
      owner_controls = ""
      if is_owner:
        owner_controls = f"""
        <div class="owner-controls">
            <button onclick="editPrayerRequest('{req_id}')">Edit</button>
            <button onclick="deletePrayerRequest('{req_id}')">Delete</button>
        </div>
        """
      html_parts.append(f"""<li class="post-it" data-id="{req_id}">
              {owner_controls}
              <p class="post-it-text">{prayer}</p>
              <div class="post-it-footer">
                  <div class="pray-container">
                      <button class="pray-button {prayed_class}">🙏</button>
                      <span class="pray-count">{pray_count}</span>
                  </div>
                  <p class="post-it-name">~ {name}</p>
              </div>
          </li>""")
    prayer_requests_html = (
        '<ul class="prayer-wall-container">\n'
        + "\n".join(html_parts)
        + "\n</ul>"
    )
  return flask.render_template(
      "prayer_wall.html", prayer_requests_html=prayer_requests_html
  )


@app.route("/update_pray_count", methods=["POST"])
def update_pray_count_route():
  """Updates prayer count for a request."""
  data = flask.request.json
  request_id = data.get("id")
  operation = data.get("operation")
  if not request_id or operation not in ("increment", "decrement"):
    return flask.jsonify({"success": False, "error": "Invalid request"}), 400
  success = prayer_requests.update_pray_count(request_id, operation)
  if success:
    if flask_login.current_user.is_authenticated:
      try:
        db = utils.get_db_client()
        user_ref = db.collection("users").document(flask_login.current_user.id)
        if operation == "increment":
          user_ref.update(
              {"prayed_request_ids": firestore.ArrayUnion([request_id])}
          )
        elif operation == "decrement":
          user_ref.update(
              {"prayed_request_ids": firestore.ArrayRemove([request_id])}
          )
      except Exception as e:
        app.logger.error(
            "Failed to update prayed_request_ids for user %s: %s",
            flask_login.current_user.id,
            e,
        )
        # We don't fail the whole request if this fails,
        # just log error. The pray count was updated.
    return flask.jsonify({"success": True})
  else:
    return (
        flask.jsonify({"success": False, "error": "Database update failed"}),
        500,
    )


@app.route("/add_prayer_request", methods=["POST"])
def add_prayer_request_route():
  """Adds a prayer request and returns confirmation or failure page."""
  name = flask.request.form.get("name")
  request = flask.request.form.get("request")
  days_ttl = flask.request.form.get("days_ttl", "30")
  if not name or not request:
    return flask.redirect("/prayer_requests")
  user_id = (
      flask_login.current_user.id
      if flask_login.current_user.is_authenticated
      else None
  )
  success, error_message = prayer_requests.add_prayer_request(
      name, request, days_ttl, user_id
  )
  if success:
    return flask.render_template("prayer_request_submitted.html")
  else:
    return flask.render_template(
        "prayer_request_failed.html", error_message=error_message
    )


@app.route("/delete_prayer_request/<request_id>", methods=["DELETE"])
@flask_login.login_required
def delete_prayer_request_route(request_id):
  """Deletes a prayer request if the current user is the owner."""
  db = utils.get_db_client()
  doc_ref = db.collection("prayer-requests").document(request_id)
  doc = doc_ref.get()
  if not doc.exists:
    return flask.jsonify({"success": False, "error": "Request not found"}), 404
  if doc.to_dict().get("user_id") != flask_login.current_user.id:
    return (
        flask.jsonify({"success": False, "error": "Permission denied"}),
        403,
    )
  doc_ref.delete()
  return flask.jsonify({"success": True})


@app.route("/save_dark_mode", methods=["POST"])
@flask_login.login_required
def save_dark_mode_route():
  """Saves dark mode preference for the current user."""
  data = flask.request.json
  dark_mode_enabled = data.get("dark_mode")
  if isinstance(dark_mode_enabled, bool):
    try:
      db = utils.get_db_client()
      user_ref = db.collection("users").document(flask_login.current_user.id)
      user_ref.set({"dark_mode": dark_mode_enabled}, merge=True)
      return flask.jsonify({"success": True})
    except Exception as e:
      app.logger.error("Failed to save dark mode setting: %s", e)
      return (
          flask.jsonify({"success": False, "error": "Database save failed"}),
          500,
      )
  return flask.jsonify({"success": False, "error": "Invalid data"}), 400


@app.route("/save_font_size", methods=["POST"])
@flask_login.login_required
def save_font_size_route():
  """Saves font size preference for the current user."""
  data = flask.request.json
  font_size_level = data.get("font_size_level")
  if isinstance(font_size_level, int):
    try:
      db = utils.get_db_client()
      user_ref = db.collection("users").document(flask_login.current_user.id)
      user_ref.set({"font_size_level": font_size_level}, merge=True)
      return flask.jsonify({"success": True})
    except Exception as e:
      app.logger.error("Failed to save font size setting: %s", e)
      return (
          flask.jsonify({"success": False, "error": "Database save failed"}),
          500,
      )
  return flask.jsonify({"success": False, "error": "Invalid data"}), 400


@app.route("/my_prayers")
@flask_login.login_required
def my_prayers_route():
  """Displays page for managing personal prayers."""
  db = utils.get_db_client()
  categories = sorted([d["topic"] for d in utils.WEEKLY_PRAYERS.values()])
  prayers_by_cat = {cat: [] for cat in categories}
  try:
    docs = (
        db.collection("personal-prayers")
        .where("user_id", "==", flask_login.current_user.id)
        .stream()
    )
    for doc in docs:
      prayer = doc.to_dict()
      prayer["id"] = doc.id
      if prayer.get("category") in prayers_by_cat:
        prayer["text"] = utils.decrypt_text(prayer["text"])
        prayers_by_cat[prayer["category"]].append(prayer)
  except Exception as e:
    app.logger.error("Failed to fetch personal prayers: %s", e)
    flask.flash("Could not load personal prayers.", "error")

  return flask.render_template(
      "my_prayers.html", prayers_by_cat=prayers_by_cat, categories=categories
  )


@app.route("/add_personal_prayer", methods=["POST"])
@flask_login.login_required
def add_personal_prayer_route():
  """Adds a personal prayer to Firestore."""
  category = flask.request.form.get("category")
  prayer_text = flask.request.form.get("prayer_text")
  categories = [d["topic"] for d in utils.WEEKLY_PRAYERS.values()]
  if not category or not prayer_text or category not in categories:
    flask.flash("Invalid category or empty prayer text.", "error")
    return flask.redirect(flask.url_for("my_prayers_route"))
  if len(prayer_text) > 1000:
    flask.flash("Prayer text cannot exceed 1000 characters.", "error")
    return flask.redirect(flask.url_for("my_prayers_route"))

  db = utils.get_db_client()
  db.collection("personal-prayers").add({
      "user_id": flask_login.current_user.id,
      "category": category,
      "text": utils.encrypt_text(prayer_text),
      "created_at": datetime.datetime.now(datetime.timezone.utc),
  })
  return flask.redirect(flask.url_for("my_prayers_route"))


@app.route("/delete_personal_prayer", methods=["POST"])
@flask_login.login_required
def delete_personal_prayer_route():
  """Deletes a personal prayer."""
  prayer_id = flask.request.form.get("prayer_id")
  if not prayer_id:
    return flask.redirect(flask.url_for("my_prayers_route"))
  db = utils.get_db_client()
  doc_ref = db.collection("personal-prayers").document(prayer_id)
  doc = doc_ref.get()
  if doc.exists and doc.to_dict().get("user_id") == flask_login.current_user.id:
    doc_ref.delete()
  else:
    flask.flash("Prayer not found or permission denied.", "error")
  return flask.redirect(flask.url_for("my_prayers_route"))


@app.route("/edit_prayer_request/<request_id>", methods=["POST"])
@flask_login.login_required
def edit_prayer_request_route(request_id):
  """Edits a prayer request if the current user is the owner."""
  data = flask.request.json
  new_request_text = data.get("request")

  success, error_message = prayer_requests.edit_prayer_request(
      request_id, new_request_text, flask_login.current_user.id
  )
  if success:
    return flask.jsonify({"success": True})
  else:
    return flask.jsonify({"success": False, "error": error_message}), 400


@app.route("/admin/traffic")
@flask_login.login_required
def admin_traffic_route():
  """Renders the admin traffic analytics page."""
  if not app.config.get(
      "ADMIN_USER_ID"
  ) or flask_login.current_user.id != app.config.get("ADMIN_USER_ID"):
    return flask.abort(403)
  return flask.render_template("admin_traffic.html")


@app.route("/admin/traffic_data")
@flask_login.login_required
def traffic_data_route():
  if not app.config.get(
      "ADMIN_USER_ID"
  ) or flask_login.current_user.id != app.config.get("ADMIN_USER_ID"):
    return flask.jsonify({"error": "Forbidden"}), 403

  try:
    db = utils.get_db_client()
    eastern_timezone = pytz.timezone("America/New_York")
    today = datetime.datetime.now(eastern_timezone).date()
    start_date = datetime.date(2025, 12, 8)

    date_strs = []
    for i in range(30):
      current_date = today - datetime.timedelta(days=i)
      if current_date >= start_date:
        date_strs.append(current_date.strftime("%Y-%m-%d"))
      else:
        # Stop if we go earlier than data collection began
        break

    if not date_strs:
      return flask.jsonify([])

    doc_refs = [db.collection("daily_analytics").document(d) for d in date_strs]
    snapshots = list(db.get_all(doc_refs))

    traffic_map = {date_str: 0 for date_str in date_strs}
    for snap in snapshots:
      if snap.exists:
        data = snap.to_dict()
        hashes = data.get("visitor_hashes") if data else None
        if isinstance(hashes, dict):
          traffic_map[snap.id] = len(hashes)

    traffic = [
        {"date": date, "count": count} for date, count in traffic_map.items()
    ]
    traffic.sort(key=lambda x: x["date"])
    return flask.jsonify(traffic)
  except Exception as e:
    app.logger.error(f"Error in traffic_data_route: {e}", exc_info=True)
    return flask.jsonify({"error": "Internal server error"}), 500


@app.after_request
def track_visitor(response):
  """Tracks unique visitors based on IP address for each HTML page loaded."""
  # Only track successful HTML page views, ignore redirects, errors, etc.
  if response.status_code == 200 and response.mimetype == "text/html":
    try:
      ip = flask.request.environ.get(
          "HTTP_X_FORWARDED_FOR", flask.request.remote_addr
      )
      eastern_timezone = pytz.timezone("America/New_York")
      date_str = datetime.datetime.now(eastern_timezone).strftime("%Y-%m-%d")
      ip_hash = hashlib.sha256(ip.encode()).hexdigest()
      db = utils.get_db_client()
      doc_ref = db.collection("daily_analytics").document(date_str)
      doc_ref.set(
          {"visitor_hashes": {ip_hash: firestore.SERVER_TIMESTAMP}}, merge=True
      )
    except Exception as e:
      app.logger.error(f"Error tracking visitor: {e}")
  return response


if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
