"""Main Flask application for serving devotions."""

import datetime
import hashlib
import os
import secrets
import uuid
import advent
from authlib.integrations.flask_client import OAuth
import bible_in_a_year
import childrens_devotion
import close_of_day
import daily_lectionary_page
import evening
import extended_evening
import flask
import flask_login
from google.cloud import firestore
import gospels_by_category
import liturgical_calendar
import memory
import mid_week
import midday
import morning
import new_year
import night_watch
import prayer_requests
import psalms_by_category
import pytz
import reminders
import secrets_fetcher
import short_prayers
import utils
import werkzeug.middleware.proxy_fix


TEMPLATE_DIR = os.path.abspath(
    os.path.join(utils.SCRIPT_DIR, "..", "templates")
)
STATIC_DIR = os.path.abspath(os.path.join(utils.SCRIPT_DIR, "..", "static"))
app = flask.Flask(
    __name__,
    template_folder=TEMPLATE_DIR,
    static_folder=STATIC_DIR,
)
app.wsgi_app = werkzeug.middleware.proxy_fix.ProxyFix(
    app.wsgi_app, x_proto=1, x_host=1
)
app.secret_key = secrets_fetcher.get_flask_secret_key()
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=31)
app.config["REMEMBER_COOKIE_DURATION"] = datetime.timedelta(days=31)
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["REMEMBER_COOKIE_SECURE"] = True
app.config["REMEMBER_COOKIE_SAMESITE"] = "None"
app.config["OTHER_PRAYERS"] = utils.get_other_prayers()
try:
  app.config["ADMIN_USER_ID"] = secrets_fetcher.get_brandon_user_id()
except:
  app.config["ADMIN_USER_ID"] = None

# OAuth and Flask-Login Setup
if app.debug:
  os.environ["AUTHLIB_INSECURE_TRANSPORT"] = "1"

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

facebook = oauth.register(
    name="facebook",
    client_id=secrets_fetcher.get_facebook_client_id(),
    client_secret=secrets_fetcher.get_facebook_client_secret(),
    access_token_url="https://graph.facebook.com/oauth/access_token",
    access_token_params=None,
    authorize_url="https://www.facebook.com/dialog/oauth",
    authorize_params=None,
    api_base_url="https://graph.facebook.com/",
    client_kwargs={"scope": "email public_profile"},
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
      favorites=None,
      fcm_tokens=None,
  ):
    self.id = user_id
    self.email = email
    self.name = name
    self.profile_pic = profile_pic
    self.dark_mode = dark_mode
    self.font_size_level = font_size_level
    self.favorites = favorites or []
    self.fcm_tokens = fcm_tokens or []

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
          favorites=data.get("favorites", []),
          fcm_tokens=data.get("fcm_tokens", []),
      )
    return None


@login_manager.user_loader
def load_user(user_id):
  """Flask-Login user loader."""
  return User.get(user_id)


@app.before_request
def redirect_to_new_domain():
  """Redirects requests from lcmsprayer.com to asimplewaytopray.com."""
  if "lcmsprayer.com" in flask.request.host:
    new_url = flask.request.url.replace(
        "lcmsprayer.com", "asimplewaytopray.com"
    )
    return flask.redirect(new_url, code=301)


@app.context_processor
def inject_globals():
  """Injects global variables into all templates."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  is_advent = now.month == 12 and 1 <= now.day <= 25
  is_new_year = (now.month == 12 and now.day == 31) or (
      now.month == 1 and now.day == 1
  )

  return dict(is_advent=is_advent, is_new_year=is_new_year)


def get_oauth_user_data(user_info, provider):
  """Extracts standard user data from OAuth info."""
  data = {}
  if provider == "google":
    data["google_id"] = user_info["sub"]
    data["email"] = user_info.get("email")
    data["name"] = user_info.get("name")
    data["profile_pic"] = user_info.get("picture")
  elif provider == "facebook":
    data["facebook_id"] = user_info["id"]
    data["email"] = user_info.get("email")
    data["name"] = user_info.get("name")
    picture_url = None
    if (
        "picture" in user_info
        and "data" in user_info["picture"]
        and "url" in user_info["picture"]["data"]
    ):
      picture_url = user_info["picture"]["data"]["url"]
    data["profile_pic"] = picture_url
  return data


def create_new_user_doc(user_data, provider):
  """Creates a new user document."""
  db = utils.get_db_client()
  if provider == "google":
    # Maintain backward compatibility: Google users use sub as doc ID
    user_id = user_data["google_id"]
  else:
    # Prefix others to avoid collision if IDs overlap (unlikely but safe)
    user_id = f"{provider}_{user_data[f'{provider}_id']}"

  user_data["last_login"] = datetime.datetime.now(datetime.timezone.utc)
  db.collection("users").document(user_id).set(user_data, merge=True)
  return User.get(user_id)


def update_existing_user_doc(user_id, user_data):
  """Updates an existing user document."""
  db = utils.get_db_client()
  user_data["last_login"] = datetime.datetime.now(datetime.timezone.utc)
  db.collection("users").document(user_id).set(user_data, merge=True)
  return User.get(user_id)


def handle_oauth_login(user_info, provider):
  """Handles the login logic including merge detection."""
  user_data = get_oauth_user_data(user_info, provider)
  email = user_data.get("email")
  provider_id_field = f"{provider}_id"
  provider_id_value = user_data[provider_id_field]

  db = utils.get_db_client()
  users_ref = db.collection("users")

  # 1. Check if user exists by this provider ID
  query = users_ref.where(provider_id_field, "==", provider_id_value).limit(1)
  results = list(query.stream())

  if results:
    # Found existing linked user
    user_doc = results[0]
    return update_existing_user_doc(user_doc.id, user_data)

  # 2. Check by email for merge opportunity
  if email:
    query_email = users_ref.where("email", "==", email).limit(1)
    email_results = list(query_email.stream())
    if email_results:
      # Found conflict/merge opportunity
      # Store info in session and redirect to merge prompt
      # We return a special signal (None, redirect_url)
      flask.session["pending_user_data"] = user_data
      flask.session["pending_provider"] = provider
      return None

  # 3. New user
  return create_new_user_doc(user_data, provider)


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
  is_new_year = (now.month == 12 and now.day == 31) or (
      now.month == 1 and now.day == 1
  )
  return flask.render_template(
      "index.html",
      is_advent=is_advent,
      is_new_year=is_new_year,
      admin_user_id=app.config.get("ADMIN_USER_ID"),
  )


@app.route("/sw.js")
def service_worker():
  """Serves the service worker file from static."""
  return app.send_static_file("sw.js")


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


@app.route("/privacy")
def privacy_route():
  """Returns the privacy policy page HTML."""
  return flask.render_template("privacy.html")


@app.route("/login")
def login():
  """Renders the sign-in page."""
  return flask.render_template("signin.html")


@app.route("/login/google")
def google_login():
  """Redirects to Google OAuth login."""
  redirect_uri = flask.url_for("authorize", _external=True)
  nonce = secrets.token_urlsafe()
  flask.session["nonce"] = nonce
  return google.authorize_redirect(redirect_uri, nonce=nonce)


@app.route("/login/facebook")
def facebook_login():
  """Redirects to Facebook OAuth login."""
  redirect_uri = flask.url_for("authorize_facebook", _external=True)
  return facebook.authorize_redirect(redirect_uri)


@app.route("/authorize")
def authorize():
  """Callback route for Google OAuth."""
  try:
    token = google.authorize_access_token()
    nonce = flask.session.pop("nonce", None)
    user_info = google.parse_id_token(token, nonce=nonce)

    result = handle_oauth_login(user_info, "google")
    if result is None:
      return flask.redirect("/login/merge")

    user = result
    flask_login.login_user(user, remember=True)
    flask.session.permanent = True
    return flask.redirect("/")
  except Exception as e:
    app.logger.warning("Google OAuth Error: %s", e)
    return "Authentication failed.", 400


@app.route("/authorize/facebook")
def authorize_facebook():
  """Callback route for Facebook OAuth."""
  app.logger.info("Processing Facebook callback")
  try:
    facebook.authorize_access_token()
    resp = facebook.get(
        "https://graph.facebook.com/me?fields=id,name,email,picture.type(large)"
    )
    user_info = resp.json()

    result = handle_oauth_login(user_info, "facebook")
    if result is None:
      return flask.redirect("/login/merge")

    user = result
    flask_login.login_user(user, remember=True)
    flask.session.permanent = True
    return flask.redirect("/")
  except Exception as e:
    app.logger.warning("Facebook OAuth Error: %s", e)
    return "Authentication failed.", 400


@app.route("/login/merge")
def merge_account_route():
  """Prompts user to merge accounts."""
  user_data = flask.session.get("pending_user_data")
  provider = flask.session.get("pending_provider")
  if not user_data or not provider:
    return flask.redirect("/login")

  return flask.render_template(
      "merge_account.html", email=user_data.get("email"), provider=provider
  )


@app.route("/login/merge/confirm", methods=["POST"])
def merge_account_confirm_route():
  """Merges the pending account into the existing one."""
  user_data = flask.session.get("pending_user_data")
  # provider = flask.session.get("pending_provider") # Unused variable
  if not user_data:
    return flask.redirect("/login")

  email = user_data.get("email")
  db = utils.get_db_client()
  users_ref = db.collection("users")

  # Find the existing user again to be safe
  query_email = users_ref.where("email", "==", email).limit(1)
  email_results = list(query_email.stream())

  if not email_results:
    # Should not happen if flow is correct, but fallback to create new
    flask.flash("Could not find account to merge. Creating new one.", "warning")
    # We don't have provider handy to call create_new_user_doc cleanly without logic duplication
    # easier to just redirect to login or handle error.
    # Actually, let's just error out safely.
    return flask.redirect("/login")

  existing_doc = email_results[0]

  # Merge data: add the new provider ID and update other fields if desired
  # We trust update_existing_user_doc to merge fields
  user = update_existing_user_doc(existing_doc.id, user_data)

  flask_login.login_user(user, remember=True)
  flask.session.permanent = True

  # Clean up session
  flask.session.pop("pending_user_data", None)
  flask.session.pop("pending_provider", None)

  return flask.redirect("/")


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


@app.route("/new_year_devotion")
def new_year_devotion_route():
  """Returns the generated devotion HTML."""
  return new_year.generate_new_year_devotion()


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


@app.route("/memory")
def memory_route():
  """Returns Scripture Memorization page."""
  return memory.generate_memory_page()


@app.route("/short_prayers")
def short_prayers_route():
  """Returns Short Prayers page."""
  return short_prayers.generate_short_prayers_page()


@app.route("/litany")
def litany_route():
  """Returns the Litany page HTML."""
  return flask.render_template("litany.html")


@app.route("/liturgical_calendar")
def liturgical_calendar_route():
  """Returns Liturgical Calendar page."""
  return liturgical_calendar.generate_liturgical_calendar_page()


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


@app.route("/daily_lectionary")
def daily_lectionary_route():
  """Returns Daily Lectionary page."""
  return daily_lectionary_page.generate_daily_lectionary_page()


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
  prayed_request_ids = []
  if flask_login.current_user.is_authenticated:
    db = utils.get_db_client()
    user_doc_ref = db.collection("users").document(flask_login.current_user.id)
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
          user_doc_ref.update({"prayed_request_ids": active_prayed_request_ids})
          prayed_request_ids = active_prayed_request_ids

  return flask.render_template(
      "prayer_wall.html",
      prayer_requests=requests,
      prayed_request_ids=prayed_request_ids,
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


@app.route("/toggle_favorite", methods=["POST"])
@flask_login.login_required
def toggle_favorite_route():
  """Toggles a favorite page for the current user."""
  data = flask.request.json
  path = data.get("path")
  title = data.get("title")

  if not path or not title:
    return (
        flask.jsonify({"success": False, "error": "Missing path or title"}),
        400,
    )

  try:
    db = utils.get_db_client()
    user_ref = db.collection("users").document(flask_login.current_user.id)

    # We need to fetch current favorites to toggle
    user_doc = user_ref.get()
    if not user_doc.exists:
      return flask.jsonify({"success": False, "error": "User not found"}), 404

    favorites = user_doc.to_dict().get("favorites", [])

    # Check if already exists (by path)
    existing_index = next(
        (i for i, f in enumerate(favorites) if f["path"] == path), -1
    )

    if existing_index >= 0:
      # Remove
      favorites.pop(existing_index)
      is_favorite = False
    else:
      # Add
      favorites.append({"path": path, "title": title})
      is_favorite = True

    user_ref.update({"favorites": favorites})
    return flask.jsonify({"success": True, "is_favorite": is_favorite})

  except Exception as e:
    app.logger.error("Failed to toggle favorite: %s", e)
    return flask.jsonify({"success": False, "error": str(e)}), 500


@app.route("/my_prayers")
@flask_login.login_required
def my_prayers_route():
  """Displays page for managing personal prayers."""
  categories = sorted([d["topic"] for d in utils.WEEKLY_PRAYERS.values()])
  prayers_by_cat = {cat: [] for cat in categories}
  try:
    raw_prayers = utils.fetch_personal_prayers(flask_login.current_user.id)
    for prayer in raw_prayers:
      if prayer.get("category") in prayers_by_cat:
        prayer["text"] = utils.decrypt_text(prayer["text"])
        if prayer.get("for_whom"):
          prayer["for_whom"] = utils.decrypt_text(prayer["for_whom"])
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
  for_whom = flask.request.form.get("for_whom")
  categories = [d["topic"] for d in utils.WEEKLY_PRAYERS.values()]
  if not category or not prayer_text or category not in categories:
    flask.flash("Invalid category or empty prayer text.", "error")
    return flask.redirect(flask.url_for("my_prayers_route"))
  if len(prayer_text) > 1000:
    flask.flash("Prayer text cannot exceed 1000 characters.", "error")
    return flask.redirect(flask.url_for("my_prayers_route"))

  db = utils.get_db_client()
  data = {
      "user_id": flask_login.current_user.id,
      "category": category,
      "text": utils.encrypt_text(prayer_text),
      "created_at": datetime.datetime.now(datetime.timezone.utc),
  }
  if for_whom:
    data["for_whom"] = utils.encrypt_text(for_whom)

  db.collection("users").document(flask_login.current_user.id).collection(
      "personal-prayers"
  ).add(data)
  return flask.redirect(flask.url_for("my_prayers_route"))


@app.route("/edit_personal_prayer", methods=["POST"])
@flask_login.login_required
def edit_personal_prayer_route():
  """Edits a personal prayer."""
  prayer_id = flask.request.form.get("prayer_id")
  category = flask.request.form.get("category")
  prayer_text = flask.request.form.get("prayer_text")
  for_whom = flask.request.form.get("for_whom")

  categories = [d["topic"] for d in utils.WEEKLY_PRAYERS.values()]

  if (
      not prayer_id
      or not category
      or not prayer_text
      or category not in categories
  ):
    flask.flash("Invalid data provided.", "error")
    return flask.redirect(flask.url_for("my_prayers_route"))

  if len(prayer_text) > 1000:
    flask.flash("Prayer text cannot exceed 1000 characters.", "error")
    return flask.redirect(flask.url_for("my_prayers_route"))

  db = utils.get_db_client()
  user_id = flask_login.current_user.id
  doc_ref = (
      db.collection("users")
      .document(user_id)
      .collection("personal-prayers")
      .document(prayer_id)
  )
  doc = doc_ref.get()

  if not doc.exists:
    flask.flash("Prayer not found or permission denied.", "error")
    return flask.redirect(flask.url_for("my_prayers_route"))

  if doc.to_dict().get("user_id") != user_id:
    flask.flash("Prayer not found or permission denied.", "error")
    return flask.redirect(flask.url_for("my_prayers_route"))

  update_data = {
      "category": category,
      "text": utils.encrypt_text(prayer_text),
  }
  if for_whom:
    update_data["for_whom"] = utils.encrypt_text(for_whom)
  else:
    update_data["for_whom"] = utils.encrypt_text("")

  doc_ref.update(update_data)
  return flask.redirect(flask.url_for("my_prayers_route"))


@app.route("/delete_personal_prayer", methods=["POST"])
@flask_login.login_required
def delete_personal_prayer_route():
  """Deletes a personal prayer."""
  prayer_id = flask.request.form.get("prayer_id")
  if not prayer_id:
    return flask.redirect(flask.url_for("my_prayers_route"))
  db = utils.get_db_client()
  user_id = flask_login.current_user.id
  doc_ref = (
      db.collection("users")
      .document(user_id)
      .collection("personal-prayers")
      .document(prayer_id)
  )
  doc = doc_ref.get()

  if doc.exists and doc.to_dict().get("user_id") == user_id:
    doc_ref.delete()
  else:
    flask.flash("Prayer not found or permission denied.", "error")
  return flask.redirect(flask.url_for("my_prayers_route"))


@app.route("/add_memory_verse", methods=["POST"])
@flask_login.login_required
def add_memory_verse_route():
  """Adds a memory verse for the current user."""
  ref = flask.request.form.get("ref")
  topic = flask.request.form.get("topic", "User Added")
  if not ref:
    flask.flash("Verse reference cannot be empty.", "error")
    return flask.redirect(flask.url_for("memory_route"))
  try:
    # Attempt to fetch to validate ref - simple validation
    utils.fetch_passages(
        [ref], include_verse_numbers=False, include_copyright=False
    )
  except:
    flask.flash(f"Could not validate reference: {ref}", "error")
    return flask.redirect(flask.url_for("memory_route"))

  db = utils.get_db_client()
  db.collection("user-memory-verses").add({
      "user_id": flask_login.current_user.id,
      "ref": ref,
      "topic": topic,
      "created_at": datetime.datetime.now(datetime.timezone.utc),
  })
  return flask.redirect(flask.url_for("memory_route"))


@app.route("/delete_memory_verse", methods=["POST"])
@flask_login.login_required
def delete_memory_verse_route():
  """Deletes a memory verse."""
  verse_id = flask.request.form.get("verse_id")
  if not verse_id:
    return flask.redirect(flask.url_for("memory_route"))
  db = utils.get_db_client()
  doc_ref = db.collection("user-memory-verses").document(verse_id)
  doc = doc_ref.get()
  if doc.exists and doc.to_dict().get("user_id") == flask_login.current_user.id:
    doc_ref.delete()
  else:
    flask.flash("Verse not found or permission denied.", "error")
  return flask.redirect(flask.url_for("memory_route"))


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


@app.route("/debug_ip")
def debug_ip_route():
  """Debug route to show visitor IP and hash."""
  if "HTTP_X_FORWARDED_FOR" in flask.request.environ:
    ip = flask.request.environ["HTTP_X_FORWARDED_FOR"].split(",")[0].strip()
    source = "HTTP_X_FORWARDED_FOR"
  else:
    ip = flask.request.remote_addr
    source = "remote_addr"

  ip_hash = hashlib.sha256(ip.encode()).hexdigest()

  return flask.jsonify({
      "ip": ip,
      "hash": ip_hash,
      "source": source,
      "headers": dict(flask.request.headers),
  })


@app.route("/reminders")
@flask_login.login_required
def reminders_route():
  """Returns the reminders page."""
  return flask.render_template("reminders.html")


@app.route("/firebase_config")
@flask_login.login_required
def firebase_config_route():
  """Returns Firebase configuration."""
  try:
    return flask.jsonify({
        "apiKey": secrets_fetcher.get_firebase_api_key(),
        "authDomain": "lcms-prayer-app.firebaseapp.com",
        "projectId": "lcms-prayer-app",
        "storageBucket": "lcms-prayer-app.firebasestorage.app",
        "messagingSenderId": secrets_fetcher.get_firebase_messaging_sender_id(),
        "appId": secrets_fetcher.get_firebase_app_id(),
        "vapidKey": secrets_fetcher.get_firebase_vapid_key(),
    })
  except Exception as e:
    app.logger.error("Failed to fetch Firebase config: %s", e)
    return flask.jsonify({"error": "Failed to fetch config"}), 500


@app.route("/save_fcm_token", methods=["POST"])
@flask_login.login_required
def save_fcm_token_route():
  """Saves an FCM token for the user."""
  data = flask.request.json
  token = data.get("token")
  if not token:
    return flask.jsonify({"success": False, "error": "Missing token"}), 400

  try:
    db = utils.get_db_client()
    user_ref = db.collection("users").document(flask_login.current_user.id)
    user_ref.update({"fcm_tokens": firestore.ArrayUnion([token])})
    return flask.jsonify({"success": True})
  except Exception as e:
    app.logger.error("Failed to save FCM token: %s", e)
    return (
        flask.jsonify({"success": False, "error": "Database save failed"}),
        500,
    )


@app.route("/remove_fcm_token", methods=["POST"])
@flask_login.login_required
def remove_fcm_token_route():
  """Removes an FCM token for the user."""
  data = flask.request.json
  token = data.get("token")
  if not token:
    return flask.jsonify({"success": False, "error": "Missing token"}), 400

  try:
    db = utils.get_db_client()
    user_ref = db.collection("users").document(flask_login.current_user.id)
    user_ref.update({"fcm_tokens": firestore.ArrayRemove([token])})
    return flask.jsonify({"success": True})
  except Exception as e:
    app.logger.error("Failed to remove FCM token: %s", e)
    return (
        flask.jsonify({"success": False, "error": "Database update failed"}),
        500,
    )


@app.route("/add_reminder", methods=["POST"])
@flask_login.login_required
def add_reminder_route():
  """Adds a prayer reminder."""
  data = flask.request.json
  # We no longer strictly need phone_number passed here if it's in the profile,
  # but we can accept it if the frontend sends it to update/verify.
  # For now, let's assume the frontend calls /save_contact_info separately
  # or we pass it through.

  success, error = reminders.add_reminder(
      flask_login.current_user.id,
      data.get("time"),
      data.get("devotion"),
      data.get("methods"),
      data.get("timezone"),
  )
  if success:
    return flask.jsonify({"success": True})
  return flask.jsonify({"success": False, "error": error}), 400


@app.route("/get_reminders")
@flask_login.login_required
def get_reminders_route():
  """Gets user reminders."""
  user_reminders = reminders.get_reminders(flask_login.current_user.id)
  return flask.jsonify(user_reminders)


@app.route("/delete_reminder", methods=["POST"])
@flask_login.login_required
def delete_reminder_route():
  """Deletes a reminder."""
  data = flask.request.json
  reminder_id = data.get("reminder_id")
  if reminders.delete_reminder(flask_login.current_user.id, reminder_id):
    return flask.jsonify({"success": True})
  return flask.jsonify({"success": False, "error": "Failed to delete"}), 500


@app.route("/tasks/send_reminders")
def send_reminders_task():
  """Cron task to send due reminders."""
  # In a real app, secure this endpoint (e.g. check for X-AppEngine-Cron header)
  reminders.send_due_reminders()
  return "OK", 200


@app.route("/debug/force_reminders", methods=["POST"])
@flask_login.login_required
def force_reminders_route():
  if flask_login.current_user.id != app.config.get("ADMIN_USER_ID"):
    return flask.abort(403)

  success, msg = reminders.force_send_reminders_for_user(
      flask_login.current_user.id
  )
  if success:
    return flask.jsonify({"success": True, "message": msg})
  else:
    return flask.jsonify({"success": False, "error": msg}), 400


@app.route("/admin/cleanup_analytics", methods=["POST"])
@flask_login.login_required
def cleanup_analytics_route():
  if not app.config.get(
      "ADMIN_USER_ID"
  ) or flask_login.current_user.id != app.config.get("ADMIN_USER_ID"):
    return flask.jsonify({"error": "Forbidden"}), 403

  try:
    deleted_count = utils.cleanup_analytics()
    return flask.jsonify(
        {"success": True, "message": f"Deleted {deleted_count} stale users."}
    )
  except Exception as e:
    app.logger.error("Cleanup analytics failed: %s", e)
    return flask.jsonify({"success": False, "error": str(e)}), 500


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
    start_date = datetime.date(2025, 12, 11)

    date_strs = []
    for i in range(30):
      current_date = today - datetime.timedelta(days=i)
      if current_date >= start_date:
        date_strs.append(current_date.strftime("%Y-%m-%d"))
      else:
        break

    if not date_strs:
      return flask.jsonify([])

    # 1. Fetch Daily Analytics
    daily_refs = [
        db.collection("daily_analytics").document(d) for d in date_strs
    ]
    daily_snapshots = list(db.get_all(daily_refs))

    # 2. Collect all User IDs involved
    user_ids_to_fetch = set()
    daily_data_map = {}  # date -> {user_id: paths}

    for snap in daily_snapshots:
      if snap.exists:
        data = snap.to_dict()
        # New format: visits is a map of user_id -> {paths: []}
        visits = data.get("visits", {})
        daily_data_map[snap.id] = visits
        for uid in visits.keys():
          user_ids_to_fetch.add(uid)
      else:
        daily_data_map[snap.id] = {}

    # 3. Fetch User Details
    users_info = {}  # user_id -> {email, ip_hashes}
    if user_ids_to_fetch:
      # Firestore 'in' query limited to 10 items, so we fetch by ID list or get_all
      # get_all allows many refs
      user_refs = [
          db.collection("analytics_users").document(uid)
          for uid in user_ids_to_fetch
      ]
      # process in chunks if necessary, but get_all handles list
      user_snapshots = list(db.get_all(user_refs))
      for snap in user_snapshots:
        if snap.exists:
          users_info[snap.id] = snap.to_dict()

    # 4. Assemble Response
    traffic = []
    for date_str in date_strs:
      visits = daily_data_map.get(date_str, {})
      visitors_list = []
      for uid, visit_data in visits.items():
        user_data = users_info.get(uid, {})
        created_at = user_data.get("created_at")
        if created_at:
          created_at = created_at.isoformat()
        visitors_list.append({
            "email": user_data.get("email"),
            "hashes": sorted(user_data.get("ip_hashes", [])),
            "paths": sorted(visit_data.get("paths", [])),
            "timestamps": sorted(visit_data.get("timestamps", [])),
            "user_agent": visit_data.get("user_agent"),
            "created_at": created_at,
        })

      traffic.append({
          "date": date_str,
          "count": len(visitors_list),
          "visitors": visitors_list,
      })

    traffic.sort(key=lambda x: x["date"])
    return flask.jsonify(traffic)
  except Exception as e:
    app.logger.error(f"Error in traffic_data_route: {e}", exc_info=True)
    return flask.jsonify({"error": "Internal server error"}), 500


@app.after_request
def track_visitor(response):
  """Tracks unique visitors using a cookie and IP address."""
  if flask.request.path == "/tasks/send_reminders":
    return response

  if response.status_code == 200 and response.mimetype == "text/html":
    try:
      # 1. Get/Set Visitor ID Cookie
      visitor_id = flask.request.cookies.get("visitor_id")
      if not visitor_id:
        visitor_id = str(uuid.uuid4())
        # Set cookie for 1 year
        expire_date = datetime.datetime.now() + datetime.timedelta(days=365)
        response.set_cookie(
            "visitor_id",
            visitor_id,
            expires=expire_date,
            httponly=True,
            samesite="Lax",
        )

      # 2. Get IP Info
      if "HTTP_X_FORWARDED_FOR" in flask.request.environ:
        ip = flask.request.environ["HTTP_X_FORWARDED_FOR"].split(",")[0].strip()
      else:
        ip = flask.request.remote_addr
      ip_hash = hashlib.sha256(ip.encode()).hexdigest()

      # 3. Analytics Logic
      eastern_timezone = pytz.timezone("America/New_York")
      current_time = datetime.datetime.now(eastern_timezone)
      date_str = current_time.strftime("%Y-%m-%d")
      timestamp = current_time.isoformat()
      path = flask.request.path
      user_agent = flask.request.headers.get("User-Agent", "Unknown")
      db = utils.get_db_client()

      # Get or Create User
      analytics_user_id = utils.get_analytics_user(
          db, visitor_id, ip_hash, flask_login.current_user
      )

      if not analytics_user_id:
        app.logger.error("Failed to get analytics_user_id")
        return response

      # Record Visit
      doc_ref = db.collection("daily_analytics").document(date_str)
      doc_ref.set(
          {
              "visits": {
                  analytics_user_id: {
                      "paths": firestore.ArrayUnion([path]),
                      "timestamps": firestore.ArrayUnion([timestamp]),
                      "user_agent": user_agent,
                  }
              }
          },
          merge=True,
      )

    except Exception as e:
      app.logger.error(f"Error tracking visitor: {e}")
  return response


if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
