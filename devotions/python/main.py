"""Main Flask application for serving devotions."""

import datetime
import logging
import os
import re
import secrets

from authlib.integrations.flask_client import OAuth
from devotional_content import advent
from devotional_content import bible_in_a_year
from devotional_content import childrens_devotion
from devotional_content import close_of_day
from devotional_content import daily_lectionary_page
from devotional_content import evening
from devotional_content import extended_evening
from devotional_content import gospels_by_category
from devotional_content import lent
from devotional_content import liturgical_calendar
from devotional_content import memory
from devotional_content import mid_week
from devotional_content import midday
from devotional_content import morning
from devotional_content import new_year
from devotional_content import nicene_creed_study
from devotional_content import night_watch
from devotional_content import psalms_by_category
from devotional_content import short_prayers
from devotional_content import small_catechism
import flask
import flask_login
from google.cloud import firestore
import liturgy
import menu
import models
import pytz
import secrets_fetcher
from services import analytics_ga4
from services import fullofeyes_scraper
from services import prayer_requests
from services import reminders
from services import users
from twilio.twiml.messaging_response import MessagingResponse
import utils
import werkzeug.middleware.proxy_fix
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash


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
    app.wsgi_app, x_proto=1, x_host=1, x_for=1, x_prefix=1
)
app.secret_key = secrets_fetcher.get_flask_secret_key()
app.config["PREFERRED_URL_SCHEME"] = "https"
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=31)
app.config["REMEMBER_COOKIE_DURATION"] = datetime.timedelta(days=31)
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["REMEMBER_COOKIE_SECURE"] = True
app.config["REMEMBER_COOKIE_SAMESITE"] = "None"
app.config["OTHER_PRAYERS"] = utils.get_other_prayers()
try:
  app.config["ADMIN_USER_ID"] = secrets_fetcher.get_brandon_user_id()
except Exception:  # pylint: disable=broad-except
  app.config["ADMIN_USER_ID"] = None

# OAuth and Flask-Login Setup
if app.debug:
  os.environ["AUTHLIB_INSECURE_TRANSPORT"] = "1"
else:
  # Wire up Gunicorn logging to Flask's logger in production
  gunicorn_logger = logging.getLogger("gunicorn.error")
  app.logger.handlers = gunicorn_logger.handlers
  app.logger.setLevel(logging.INFO)

  # Configure root logger to output to Gunicorn handlers as well
  # This ensures logs from other modules (like fullofeyes_scraper) are captured
  root_logger = logging.getLogger()
  root_logger.handlers = gunicorn_logger.handlers
  root_logger.setLevel(logging.INFO)

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


@login_manager.user_loader
def load_user(user_id):
  """Flask-Login user loader."""
  return models.User.get(user_id)


@app.before_request
def log_request_info():
  """Logs details about the incoming request for debugging."""
  app.logger.info(
      f"Incoming Request: {flask.request.method} {flask.request.url}"
  )


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
  timezone_str = "America/New_York"
  if (
      flask_login.current_user.is_authenticated
      and flask_login.current_user.timezone
  ):
    timezone_str = flask_login.current_user.timezone

  try:
    tz = pytz.timezone(timezone_str)
  except pytz.UnknownTimeZoneError:
    tz = pytz.timezone("America/New_York")

  now = datetime.datetime.now(tz)
  is_advent = now.month == 12 and 1 <= now.day <= 25
  is_new_year = (now.month == 12 and now.day == 31) or (
      now.month == 1 and now.day == 1
  )

  cy = liturgy.ChurchYear(now.year)
  ash_wednesday = cy.ash_wednesday
  easter_sunday = cy.easter_date
  is_lent = ash_wednesday <= now.date() <= easter_sunday

  app_menu = menu.get_menu_items(is_advent, is_new_year, is_lent)
  today_ymd = now.strftime("%Y-%m-%d")

  return dict(
      is_advent=is_advent,
      is_new_year=is_new_year,
      is_lent=is_lent,
      app_menu=app_menu,
      today_ymd=today_ymd,
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
  timezone_str = "America/New_York"
  if (
      flask_login.current_user.is_authenticated
      and flask_login.current_user.timezone
  ):
    timezone_str = flask_login.current_user.timezone

  try:
    tz = pytz.timezone(timezone_str)
  except pytz.UnknownTimeZoneError:
    tz = pytz.timezone("America/New_York")

  now = datetime.datetime.now(tz)
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
  if flask_login.current_user.is_authenticated:
    return flask.redirect("/settings")
  return flask.render_template("signin.html")


@app.route("/settings")
def settings_route():
  """Renders the dedicated settings page."""
  if flask.request.args.get("demo") == "twilio_compliance":
    dummy_user = models.User(
        user_id="demo_user",
        email="demo@asimplewaytopray.com",
        name="Demo User",
        phone_number="+15550199999",
        notification_preferences={
            "prayer_reminders": {"push": True, "email": False, "sms": False},
            "prayed_for_me": {"push": True, "email": False, "sms": False},
        },
        timezone="America/New_York",
    )
    return flask.render_template(
        "settings.html",
        timezones=pytz.common_timezones,
        current_user=dummy_user,
    )

  return flask.render_template("settings.html", timezones=pytz.common_timezones)


@app.route("/settings/update_profile", methods=["POST"])
@flask_login.login_required
def update_profile():
  """Updates user profile (name, email, phone)."""
  name = flask.request.form.get("name")
  email = flask.request.form.get("email", "").strip().lower()
  phone = flask.request.form.get("phone")

  if not name or not email:
    flask.flash("Name and Email are required.", "error")
    return flask.redirect("/settings")

  email_error = users.validate_email(email)
  if email_error:
    flask.flash(email_error, "error")
    return flask.redirect("/settings")

  # Basic phone validation/cleanup
  if phone:
    cleaned_phone = re.sub(r"[^\d+]", "", phone)
    if cleaned_phone and not cleaned_phone.startswith("+"):
      if len(cleaned_phone) == 10:
        cleaned_phone = "+1" + cleaned_phone
      else:
        cleaned_phone = "+" + cleaned_phone
    phone = cleaned_phone
  else:
    phone = None  # Explicitly set to None if empty string to clear it or handle properly

  try:
    db = utils.get_db_client()

    # Check uniqueness if email changed
    if email != flask_login.current_user.email:
      users_ref = db.collection("users")
      query = users_ref.where("email", "==", email).limit(1)
      if list(query.stream()):
        flask.flash("Email already in use.", "error")
        return flask.redirect("/settings")

    user_ref = db.collection("users").document(flask_login.current_user.id)
    update_data = {"name": name, "email": email}
    if phone is not None:
      update_data["phone_number"] = phone

    user_ref.update(update_data)
    flask.flash("Profile updated successfully.", "success")
  except Exception as e:
    app.logger.error("Failed to update profile: %s", e)
    flask.flash("An error occurred while updating profile.", "error")

  return flask.redirect("/settings")


@app.route("/settings/save_notification_preferences", methods=["POST"])
@flask_login.login_required
def save_notification_preferences():
  """Saves notification preferences."""
  data = flask.request.json
  preferences = data.get("preferences")
  timezone = data.get("timezone")

  if not preferences:
    return flask.jsonify({"success": False, "error": "No data provided"}), 400

  try:
    db = utils.get_db_client()
    user_ref = db.collection("users").document(flask_login.current_user.id)
    updates = {"notification_preferences": preferences}

    if timezone:
      updates["timezone"] = timezone
      # If timezone changed, update all existing reminders
      if timezone != flask_login.current_user.timezone:
        reminders.update_user_reminders_timezone(
            flask_login.current_user.id, timezone
        )

    user_ref.update(updates)
    return flask.jsonify({"success": True})
  except Exception as e:
    app.logger.error("Failed to save preferences: %s", e)
    return flask.jsonify({"success": False, "error": str(e)}), 500


@app.route("/settings/export_data")
@flask_login.login_required
def export_data_route():
  """Exports user's personal prayers as JSON."""
  try:
    prayers = utils.fetch_personal_prayers(flask_login.current_user.id)
    # Decrypt for export
    export_list = []
    for p in prayers:
      p_export = p.copy()
      if "text" in p_export:
        p_export["text"] = utils.decrypt_text(p_export["text"])
      if "for_whom" in p_export and p_export["for_whom"]:
        p_export["for_whom"] = utils.decrypt_text(p_export["for_whom"])
      export_list.append(p_export)

    response = flask.jsonify(export_list)
    response.headers["Content-Disposition"] = (
        "attachment; filename=my_prayers_export.json"
    )
    return response
  except Exception as e:
    app.logger.error("Failed to export data: %s", e)
    return "Failed to export data", 500


@app.route("/settings/update_picture", methods=["POST"])
@flask_login.login_required
def update_picture():
  """Updates selected profile picture."""
  source = flask.request.form.get("pic_source")
  custom_url = flask.request.form.get("custom_pic_url")

  updates = {}

  if source == "google":
    if flask_login.current_user.google_profile_pic:
      updates["profile_pic"] = flask_login.current_user.google_profile_pic
      updates["selected_pic_source"] = "google"
  elif source == "custom":
    if custom_url:
      updates["profile_pic"] = custom_url
      updates["selected_pic_source"] = "custom"

  if updates:
    try:
      db = utils.get_db_client()
      user_ref = db.collection("users").document(flask_login.current_user.id)
      user_ref.update(updates)
      flask.flash("Profile picture updated.", "success")
    except Exception as e:
      app.logger.error("Failed to update picture: %s", e)
      flask.flash("Error updating picture.", "error")

  return flask.redirect("/settings")


@app.route("/settings/update_password", methods=["POST"])
@flask_login.login_required
def update_password():
  """Updates or sets the user's password."""
  current_password = flask.request.form.get("current_password")
  new_password = flask.request.form.get("new_password")
  confirm_new_password = flask.request.form.get("confirm_new_password")

  if not new_password or not confirm_new_password:
    flask.flash("New password and confirmation are required.", "error")
    return flask.redirect("/settings")

  if new_password != confirm_new_password:
    flask.flash("New passwords do not match.", "error")
    return flask.redirect("/settings")

  password_error = users.validate_password(new_password)
  if password_error:
    flask.flash(password_error, "error")
    return flask.redirect("/settings")

  user = flask_login.current_user
  db = utils.get_db_client()
  user_ref = db.collection("users").document(user.id)

  if user.password_hash:
    if not current_password:
      flask.flash("Current password is required.", "error")
      return flask.redirect("/settings")
    if not check_password_hash(user.password_hash, current_password):
      flask.flash("Incorrect current password.", "error")
      return flask.redirect("/settings")

  hashed_password = generate_password_hash(new_password)
  user_ref.update({"password_hash": hashed_password})

  flask.flash("Password updated successfully.", "success")
  return flask.redirect("/settings")


@app.route("/login/google")
def google_login():
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

    if flask_login.current_user.is_authenticated:
      # Link account logic
      user_data = users.get_oauth_user_data(user_info, "google")
      # Check if this google ID is already used by another user
      db = utils.get_db_client()
      users_ref = db.collection("users")
      query = users_ref.where("google_id", "==", user_data["google_id"]).limit(
          1
      )
      results = list(query.stream())

      if results:
        existing_doc = results[0]
        if existing_doc.id != flask_login.current_user.id:
          flask.flash(
              "This Google account is already linked to another user.", "error"
          )
          return flask.redirect("/settings")
        # If same user, update info
        users.update_existing_user_doc(flask_login.current_user.id, user_data)
        flask.flash("Google account refreshed.", "success")
        return flask.redirect("/settings")
      else:
        # Link it
        users.update_existing_user_doc(flask_login.current_user.id, user_data)
        flask.flash("Google account linked successfully.", "success")
        return flask.redirect("/settings")

    result = users.handle_oauth_login(user_info, "google")
    if result is None:
      return flask.redirect("/login/merge")

    user = result
    flask_login.login_user(user, remember=True)
    flask.session.permanent = True
    return flask.redirect("/")
  except Exception as e:
    app.logger.warning("Google OAuth Error: %s", e)
    return "Authentication failed.", 400


@app.route("/register", methods=["GET", "POST"])
def register():
  """Handles user registration."""
  if flask_login.current_user.is_authenticated:
    return flask.redirect("/")

  if flask.request.method == "GET":
    return flask.render_template("register.html")

  name = flask.request.form.get("name")
  email = flask.request.form.get("email", "").strip().lower()
  password = flask.request.form.get("password")
  confirm_password = flask.request.form.get("confirm_password")

  if not name or not email or not password or not confirm_password:
    flask.flash("All fields are required.", "error")
    return flask.render_template("register.html")

  email_error = users.validate_email(email)
  if email_error:
    flask.flash(email_error, "error")
    return flask.render_template("register.html")

  if password != confirm_password:
    flask.flash("Passwords do not match.", "error")
    return flask.render_template("register.html")

  password_error = users.validate_password(password)
  if password_error:
    flask.flash(password_error, "error")
    return flask.render_template("register.html")

  db = utils.get_db_client()
  users_ref = db.collection("users")

  # Check if email already exists
  query_email = users_ref.where("email", "==", email).limit(1)
  email_results = list(query_email.stream())

  if email_results:
    existing_user_doc = email_results[0]
    existing_data = existing_user_doc.to_dict()

    # If user exists but has no password (e.g. Google user), allow "merge" by setting password
    if not existing_data.get("password_hash"):
      # We still verify email even for merge to ensure ownership
      pass  # Continue to verification flow
    else:
      flask.flash("Account with this email already exists.", "error")
      return flask.render_template("register.html")

  # Generate verification code
  verification_code = "".join([str(secrets.randbelow(10)) for _ in range(6)])
  hashed_password = generate_password_hash(password)

  # Store pending data in session
  flask.session["pending_registration"] = {
      "name": name,
      "email": email,
      "password_hash": hashed_password,
      "code": verification_code,
      "is_merge": bool(email_results),
      "merge_user_id": email_results[0].id if email_results else None,
  }

  users.send_verification_email(email, verification_code)
  return flask.redirect("/register/verify")


@app.route("/register/verify", methods=["GET", "POST"])
def register_verify():
  """Handles email verification step."""
  pending_data = flask.session.get("pending_registration")
  if not pending_data:
    flask.flash("Registration session expired. Please start over.", "error")
    return flask.redirect("/register")

  if flask.request.method == "GET":
    return flask.render_template(
        "verify_email.html", email=pending_data["email"]
    )

  code = flask.request.form.get("code", "").strip()
  if code == pending_data["code"]:
    # Verification successful
    db = utils.get_db_client()
    users_ref = db.collection("users")

    if pending_data.get("is_merge"):
      # Merge logic
      user_id = pending_data["merge_user_id"]
      users_ref.document(user_id).update({
          "password_hash": pending_data["password_hash"],
          "name": pending_data["name"],
      })
      user = models.User.get(user_id)
      flask.flash("Account verified and updated!", "success")
    else:
      # Create new user
      user_data = {
          "name": pending_data["name"],
          "email": pending_data["email"],
          "password_hash": pending_data["password_hash"],
          "created_at": datetime.datetime.now(datetime.timezone.utc),
      }
      user = users.create_new_user_doc(user_data, "email")
      flask.flash("Account created successfully!", "success")

    flask_login.login_user(user, remember=True)
    flask.session.pop("pending_registration", None)
    return flask.redirect("/")
  else:
    flask.flash("Invalid verification code. Please try again.", "error")
    return flask.render_template(
        "verify_email.html", email=pending_data["email"]
    )


@app.route("/login/email", methods=["POST"])
def email_login():
  """Handles email/password login."""
  email = flask.request.form.get("email", "").strip().lower()
  password = flask.request.form.get("password")

  if not email or not password:
    flask.flash("Email and password are required.", "error")
    return flask.redirect("/login")

  db = utils.get_db_client()
  users_ref = db.collection("users")
  query_email = users_ref.where("email", "==", email).limit(1)
  email_results = list(query_email.stream())

  if not email_results:
    flask.flash("Invalid email or password.", "error")
    return flask.redirect("/login")

  user_doc = email_results[0]
  user_data = user_doc.to_dict()
  stored_hash = user_data.get("password_hash")

  if not stored_hash or not check_password_hash(stored_hash, password):
    flask.flash("Invalid email or password.", "error")
    return flask.redirect("/login")

  user = models.User.get(user_doc.id)
  flask_login.login_user(user, remember=True)
  return flask.redirect("/")


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password_route():
  """Handles forgotten password requests."""
  if flask.request.method == "POST":
    email = flask.request.form.get("email", "").strip().lower()
    if not email:
      flask.flash("Please enter an email address.", "error")
      return flask.render_template("forgot_password.html")

    user = users.get_user_by_email(email)
    if user:
      token = users.get_reset_token(email)
      reset_link = flask.url_for(
          "reset_password_route", token=token, _external=True
      )
      users.send_password_reset_email(email, reset_link)

    flask.flash(
        "If an account with that email exists, a password reset link has been"
        " sent.",
        "success",
    )
    return flask.redirect("/login")

  return flask.render_template("forgot_password.html")


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password_route(token):
  """Handles password reset with token."""
  email = users.verify_reset_token(token)
  if not email:
    flask.flash("The password reset link is invalid or has expired.", "error")
    return flask.redirect("/forgot_password")

  if flask.request.method == "POST":
    password = flask.request.form.get("password")
    confirm_password = flask.request.form.get("confirm_password")

    if not password or not confirm_password:
      flask.flash("Please fill out all fields.", "error")
      return flask.render_template("reset_password.html")

    if password != confirm_password:
      flask.flash("Passwords do not match.", "error")
      return flask.render_template("reset_password.html")

    password_error = users.validate_password(password)
    if password_error:
      flask.flash(password_error, "error")
      return flask.render_template("reset_password.html")

    hashed_password = generate_password_hash(password)
    if users.reset_password(email, hashed_password):
      flask.flash(
          "Your password has been updated! You can now log in.", "success"
      )
      return flask.redirect("/login")
    else:
      flask.flash("An error occurred. Please try again.", "error")

  return flask.render_template("reset_password.html")


@app.route("/complete_prayer_email/<token>")
def complete_prayer_email_route(token):
  """Marks prayer as complete from an email link."""
  data = users.verify_completion_token(token)
  if not data:
    return (
        (
            "Invalid or expired token. You may have already completed this"
            " prayer or waited too long."
        ),
        400,
    )

  user_id = data.get("uid")
  devotion_type = data.get("dt")
  bible_year_day = data.get("byd")

  # We use the user's stored timezone or default
  user = models.User.get(user_id)
  if not user:
    return "User not found.", 404

  timezone_str = user.timezone or "America/New_York"
  result = users.process_prayer_completion(
      user_id, devotion_type, timezone_str, bible_year_day
  )

  if result:
    msg = result.get("message", "Prayer recorded!")
    streak = result.get("streak", 0)
    # Simple HTML response
    return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: sans-serif; text-align: center; padding: 40px 20px; background-color: #f9f8f4; }}
                .card {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 400px; margin: 0 auto; }}
                h1 {{ color: #27ae60; }}
                p {{ color: #555; font-size: 1.1em; }}
                .streak {{ font-size: 2em; font-weight: bold; color: #e67e22; margin: 20px 0; }}
                .button {{ display: inline-block; padding: 10px 20px; background-color: #2980b9; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>✓ Prayer Recorded</h1>
                <p>{msg}</p>
                <div class="streak">🔥 {streak} Day Streak</div>
                <a href="/" class="button">Go to App</a>
            </div>
        </body>
        </html>
        """
  else:
    return "Failed to record prayer.", 500


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
  user = users.update_existing_user_doc(existing_doc.id, user_data)

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


def get_date_from_request():
  """Parses 'date' query parameter."""
  date_str = flask.request.args.get("date")
  if date_str:
    try:
      return datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
      pass
  return None


@app.route("/extended_evening_devotion")
def extended_evening_devotion_route():
  """Returns the generated devotion HTML."""
  return extended_evening.generate_extended_evening_devotion(
      get_date_from_request()
  )


@app.route("/morning_devotion")
def morning_devotion_route():
  """Returns the generated devotion HTML."""
  return morning.generate_morning_devotion(get_date_from_request())


@app.route("/midday_devotion")
def midday_devotion_route():
  """Returns the generated devotion HTML."""
  return midday.generate_midday_devotion(get_date_from_request())


@app.route("/evening_devotion")
def evening_devotion_route():
  """Returns the generated devotion HTML."""
  return evening.generate_evening_devotion(get_date_from_request())


@app.route("/close_of_day_devotion")
def close_of_day_devotion_route():
  """Returns the generated devotion HTML."""
  return close_of_day.generate_close_of_day_devotion(get_date_from_request())


@app.route("/mid_week_devotion")
def mid_week_devotion_route():
  """Returns the generated mid-week devotion HTML."""
  return mid_week.generate_mid_week_devotion(get_date_from_request())


@app.route("/advent_devotion")
def advent_devotion_route():
  """Returns the generated devotion HTML."""
  return advent.generate_advent_devotion(get_date_from_request())


@app.route("/lent_devotion")
def lent_devotion_route():
  """Returns the generated devotion HTML."""
  return lent.generate_lent_devotion(get_date_from_request())


@app.route("/new_year_devotion")
def new_year_devotion_route():
  """Returns the generated devotion HTML."""
  return new_year.generate_new_year_devotion(get_date_from_request())


@app.route("/childrens_devotion")
def childrens_devotion_route():
  """Returns the generated children's devotion HTML."""
  # Children's devotion doesn't vary by date in the same way, but could if needed.
  return childrens_devotion.generate_childrens_devotion()


@app.route("/night_watch_devotion")
def night_watch_devotion_route():
  """Returns the generated devotion HTML."""
  return night_watch.generate_night_watch_devotion(get_date_from_request())


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
    app.logger.error(f"Error in get_passage_text: {e}")
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


@app.route("/small_catechism")
def small_catechism_route():
  """Returns Small Catechism page."""
  return small_catechism.generate_small_catechism_page()


@app.route("/nicene_creed_study")
def nicene_creed_study_route():
  """Returns Nicene Creed Study page."""
  return nicene_creed_study.generate_nicene_creed_study_page()


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
  completed_days = []
  bible_streak = 0

  if flask_login.current_user.is_authenticated:
    db = utils.get_db_client()
    doc = db.collection("users").document(flask_login.current_user.id).get()
    if doc.exists:
      data = doc.to_dict()
      bia_progress = data.get("bia_progress")
      completed_days = data.get("completed_bible_days", [])
      bible_streak = data.get("bible_streak_count", 0)

  return bible_in_a_year.generate_bible_in_a_year_page(
      bia_progress, completed_days, bible_streak
  )


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
      utils.save_bia_progress(flask_login.current_user.id, day, last_visit)
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
    app.logger.error(f"Error removing expired prayer requests: {e}")
  active_requests = prayer_requests.get_prayer_wall_requests(limit=10)
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
      prayer_requests=active_requests,
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
    # 1. Update current user's prayed history and check achievements
    if flask_login.current_user.is_authenticated:
      try:
        # This handles both updating the list and checking achievements
        users.record_prayer_for_others(
            flask_login.current_user.id, request_id, operation
        )
      except Exception as e:
        app.logger.error(
            "Failed to record prayer for others user %s: %s",
            flask_login.current_user.id,
            e,
        )

    # 2. Send "Someone prayed for you" notification (on increment only)
    if operation == "increment":
      try:
        # We need to find the owner of the prayer request
        # Fetching it here directly to avoid circular dependency or adding more to prayer_requests.py
        db = utils.get_db_client()
        req_doc = db.collection("prayer-requests").document(request_id).get()
        if req_doc.exists:
          req_data = req_doc.to_dict()
          owner_id = req_data.get("user_id")
          # Don't notify if the user is praying for their own request
          if owner_id and (
              not flask_login.current_user.is_authenticated
              or owner_id != flask_login.current_user.id
          ):
            request_text = req_data.get("request", "")
            # Truncate request text for notification body
            if len(request_text) > 100:
              request_text = request_text[:100] + "..."

            reminders.send_generic_notification_to_user(
                owner_id,
                "Someone prayed for you!",
                f'Someone just prayed for your request: "{request_text}"',
                "/prayer_wall",  # Link them back to the wall
                "prayed_for_me",
            )
      except Exception as e:
        app.logger.error(f"Failed to send prayer notification: {e}")

    return flask.jsonify({"success": True})
  else:
    return (
        flask.jsonify({"success": False, "error": "Database update failed"}),
        500,
    )


@app.route("/add_prayer_request", methods=["POST"])
@flask_login.login_required
def add_prayer_request_route():
  """Adds a prayer request and returns confirmation or failure page."""
  name = flask.request.form.get("name")
  request = flask.request.form.get("request")
  days_ttl = flask.request.form.get("days_ttl", "30")
  if not name or not request:
    return flask.redirect("/prayer_requests")

  user_id = flask_login.current_user.id

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


@app.route("/save_background_art", methods=["POST"])
@flask_login.login_required
def save_background_art_route():
  """Saves background art preference for the current user."""
  data = flask.request.json
  enabled = data.get("background_art")
  if isinstance(enabled, bool):
    try:
      db = utils.get_db_client()
      user_ref = db.collection("users").document(flask_login.current_user.id)
      user_ref.set({"background_art": enabled}, merge=True)
      return flask.jsonify({"success": True})
    except Exception as e:
      app.logger.error("Failed to save background art setting: %s", e)
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
def my_prayers_route():
  """Displays page for managing personal prayers."""
  categories = sorted([d["topic"] for d in utils.WEEKLY_PRAYERS.values()])
  prayers_by_cat = {cat: [] for cat in categories}

  if flask_login.current_user.is_authenticated:
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
  """Renders the GA4 traffic analytics page."""
  if not app.config.get(
      "ADMIN_USER_ID"
  ) or flask_login.current_user.id != app.config.get("ADMIN_USER_ID"):
    return flask.abort(403)

  # Fetch registered users from Firestore
  registered_users = []
  registered_user_count = 0
  try:
    db = utils.get_db_client()
    users_ref = db.collection("users")
    # Fetch all users
    docs = users_ref.stream()

    eastern_timezone = pytz.timezone("America/New_York")

    for doc in docs:
      data = doc.to_dict()
      last_login = data.get("last_login")
      last_login_val = datetime.datetime.min.replace(
          tzinfo=datetime.timezone.utc
      )
      last_login_str = "Never"

      if last_login:
        if isinstance(last_login, datetime.datetime):
          # Ensure aware
          if last_login.tzinfo is None:
            last_login = last_login.replace(tzinfo=datetime.timezone.utc)
          last_login_est = last_login.astimezone(eastern_timezone)
          last_login_str = last_login_est.strftime("%Y-%m-%d %I:%M %p")
          last_login_val = last_login
        else:
          last_login_str = str(last_login)

      registered_users.append({
          "name": data.get("name", "Unknown"),
          "email": data.get("email", "Unknown"),
          "last_login": last_login_str,
          "_sort_key": last_login_val,
      })

    # Sort in memory by last login descending
    registered_users.sort(key=lambda x: x["_sort_key"], reverse=True)
    registered_user_count = len(registered_users)

  except Exception as e:
    app.logger.error(f"Error fetching users: {e}")

  try:
    property_id = secrets_fetcher.get_ga4_property_id()
    data = analytics_ga4.fetch_traffic_stats(property_id)
    data["registered_user_count"] = registered_user_count
    data["registered_users"] = registered_users
    return flask.render_template("admin_traffic.html", **data)
  except Exception as e:
    # If fetch fails (e.g. secret not set), return error info
    return flask.render_template(
        "admin_traffic.html",
        error=str(e),
        service_email=analytics_ga4.get_service_account_email(),
        registered_user_count=registered_user_count,
        registered_users=registered_users,
    )


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


@app.route("/api/lectionary/art")
def lectionary_art_route():
  """Fetches relevant art based on a query."""
  ref = flask.request.args.get("ref")
  theme = flask.request.args.get("theme")
  art = fullofeyes_scraper.get_art_for_reading(ref, fallback_theme=theme)
  return flask.jsonify(art) if art else flask.jsonify({})


@app.route("/api/art/recent")
def art_recent_route():
  """Fetches a random recent image."""
  ttl_key = int(datetime.datetime.now().timestamp() // 3600)
  images = fullofeyes_scraper.fetch_recent_images_cached(ttl_key)
  if images:
    return flask.jsonify(secrets.choice(images))
  return flask.jsonify({})


@app.route("/api/complete_prayer", methods=["POST"])
@flask_login.login_required
def complete_prayer_route():
  """Marks a prayer as complete and updates the streak."""
  data = flask.request.json
  devotion_type = data.get("devotion_type", "unknown")
  bible_year_day = data.get("bible_year_day")

  user_id = flask_login.current_user.id
  timezone_str = flask_login.current_user.timezone or "America/New_York"

  result = users.process_prayer_completion(
      user_id, devotion_type, timezone_str, bible_year_day
  )

  if result:
    return flask.jsonify(result)
  else:
    return flask.jsonify({"error": "User not found"}), 404


@app.route("/api/complete_bible_reading", methods=["POST"])
@flask_login.login_required
def complete_bible_reading_route():
  """Marks a Bible reading as complete."""
  data = flask.request.json
  day = data.get("day")
  if not day:
    return flask.jsonify({"error": "Missing day"}), 400

  user_id = flask_login.current_user.id
  timezone_str = flask_login.current_user.timezone or "America/New_York"

  result = users.process_bible_reading_completion(user_id, day, timezone_str)
  if result:
    return flask.jsonify(result)
  else:
    return flask.jsonify({"error": "Failed to update"}), 500


@app.route("/api/catch_up_bible_readings", methods=["POST"])
@flask_login.login_required
def catch_up_bible_readings_route():
  """Marks multiple Bible readings as complete."""
  data = flask.request.json
  days = data.get("days")
  if not days or not isinstance(days, list):
    return flask.jsonify({"error": "Invalid days list"}), 400

  user_id = flask_login.current_user.id
  result = users.mark_bible_days_completed(user_id, days)

  if result:
    return flask.jsonify(result)
  else:
    return flask.jsonify({"error": "Failed to update"}), 500


@app.route("/api/toggle_memorized_verse", methods=["POST"])
@flask_login.login_required
def toggle_memorized_verse_route():
  """Toggles the memorized status of a verse."""
  data = flask.request.json
  verse_id = data.get("verse_id")
  if not verse_id:
    return flask.jsonify({"error": "Missing verse_id"}), 400

  result = users.toggle_memorized_verse(flask_login.current_user.id, verse_id)
  if result:
    return flask.jsonify(result)
  return flask.jsonify({"error": "Failed"}), 500


@app.route("/api/mark_catechism_complete", methods=["POST"])
@flask_login.login_required
def mark_catechism_complete_route():
  """Marks a catechism section as complete."""
  data = flask.request.json
  section_index = data.get("section_index")
  if section_index is None:
    return flask.jsonify({"error": "Missing section_index"}), 400

  result = users.mark_catechism_complete(
      flask_login.current_user.id, section_index
  )
  if result:
    return flask.jsonify(result)
  return flask.jsonify({"error": "Failed"}), 500


@app.route("/streaks")
@flask_login.login_required
def streaks_route():
  """Renders the streaks and achievements page."""
  user = flask_login.current_user

  # Prayer Streak Logic
  current_streak = user.streak_count
  next_milestone = 7
  milestones = [7, 30, 90, 180, 270, 365]

  for m in milestones:
    if current_streak < m:
      next_milestone = m
      break
  if current_streak >= 365:
    next_milestone = current_streak + (90 - ((current_streak - 365) % 90))

  progress_percent = min(100, (current_streak / next_milestone) * 100)

  # Bible Streak Logic
  bible_streak = getattr(user, "bible_streak_count", 0)
  bible_next_milestone = 7
  for m in milestones:
    if bible_streak < m:
      bible_next_milestone = m
      break
  if bible_streak >= 365:
    bible_next_milestone = bible_streak + (90 - ((bible_streak - 365) % 90))

  bible_progress_percent = min(100, (bible_streak / bible_next_milestone) * 100)

  # Gamification Stats
  prayed_for_others_count = len(user.prayed_request_ids)
  memorized_verses_count = len(user.memorized_verses)

  catechism_total = len(utils.CATECHISM_SECTIONS)
  catechism_completed = len(user.completed_catechism_sections)
  catechism_pct = 0
  if catechism_total > 0:
    catechism_pct = int((catechism_completed / catechism_total) * 100)

  # Determine if prayed today
  timezone_str = user.timezone or "America/New_York"
  try:
    tz = pytz.timezone(timezone_str)
  except pytz.UnknownTimeZoneError:
    tz = pytz.timezone("America/New_York")

  today_str = datetime.datetime.now(tz).strftime("%Y-%m-%d")
  prayed_today = user.last_prayer_date == today_str

  # Determine if read bible today
  read_bible_today = user.last_bible_reading_date == today_str

  # Count devotions today
  devotions_today_count = 0
  if user.completed_devotions:
    for ts_str in user.completed_devotions.values():
      if ts_str.startswith(today_str):
        devotions_today_count += 1

  # Determine recommended devotion
  now = datetime.datetime.now(tz)
  hour = now.hour
  if 5 <= hour < 11:
    recommended_devotion = {
        "name": "Morning Prayer",
        "url": "/morning_devotion",
    }
  elif 11 <= hour < 15:
    recommended_devotion = {"name": "Midday Prayer", "url": "/midday_devotion"}
  elif 15 <= hour < 20:
    recommended_devotion = {
        "name": "Evening Prayer",
        "url": "/evening_devotion",
    }
  elif 0 <= hour < 5:
    recommended_devotion = {
        "name": "Night Watch",
        "url": "/night_watch_devotion",
    }
  else:
    recommended_devotion = {
        "name": "Close of the Day",
        "url": "/close_of_day_devotion",
    }

  return flask.render_template(
      "streaks.html",
      current_streak=current_streak,
      next_milestone=next_milestone,
      progress_percent=progress_percent,
      prayed_today=prayed_today,
      devotions_today_count=devotions_today_count,
      achievements=user.achievements,
      recommended_devotion=recommended_devotion,
      bible_streak=bible_streak,
      read_bible_today=read_bible_today,
      bible_next_milestone=bible_next_milestone,
      bible_progress_percent=bible_progress_percent,
      prayed_for_others_count=prayed_for_others_count,
      memorized_verses_count=memorized_verses_count,
      catechism_completed=catechism_completed,
      catechism_total=catechism_total,
      catechism_pct=catechism_pct,
  )


@app.route("/twilio/sms_reply", methods=["POST"])
def twilio_sms_reply():
  """Handles incoming SMS replies from Twilio."""
  incoming_msg = flask.request.values.get("Body", "").strip().upper()
  from_number = flask.request.values.get("From", "")

  resp = MessagingResponse()

  if incoming_msg == "STOP":
    # Logic to find user and disable SMS for the last sent type
    try:
      db = utils.get_db_client()
      users_ref = db.collection("users")
      # Query by phone number
      query = users_ref.where("phone_number", "==", from_number).limit(1)
      results = list(query.stream())

      if results:
        user_doc = results[0]
        user_data = user_doc.to_dict()
        last_type = user_data.get("last_sms_type")

        if last_type:
          # Update preference
          current_prefs = user_data.get("notification_preferences", {})
          if last_type in current_prefs:
            current_prefs[last_type]["sms"] = False
            user_doc.reference.update(
                {"notification_preferences": current_prefs}
            )

            readable_type = last_type.replace("_", " ").title()
            resp.message(
                f"You have been unsubscribed from {readable_type} SMS"
                " notifications."
            )
          else:
            resp.message("You have been unsubscribed from SMS notifications.")
        else:
          # Fallback: Disable all SMS? Or just generic message.
          # Let's assume generic stop for now if we can't find the type.
          # Or maybe we shouldn't modify anything if we don't know what to stop,
          # but Twilio might block us anyway.
          # Best effort: disable 'prayer_reminders' as default
          current_prefs = user_data.get("notification_preferences", {})
          updated = False
          if "prayer_reminders" in current_prefs:
            current_prefs["prayer_reminders"]["sms"] = False
            updated = True

          if updated:
            user_doc.reference.update(
                {"notification_preferences": current_prefs}
            )
            resp.message("You have been unsubscribed from SMS reminders.")
          else:
            resp.message("You have been unsubscribed.")

      else:
        app.logger.warning(
            f"Twilio STOP received from unknown number: {from_number}"
        )
        resp.message("You have been unsubscribed.")

    except Exception as e:
      app.logger.error(f"Error handling Twilio reply: {e}")
      resp.message("Error processing request.")

  return str(resp)


if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
