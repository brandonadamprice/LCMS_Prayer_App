"""Main Flask application for serving devotions."""

import datetime
import functools
import logging
import os
import re
import secrets

from authlib.integrations.flask_client import OAuth
from devotional_content import advent
from devotional_content import bible_in_a_year
from devotional_content import catechism_memory
from devotional_content import childrens_devotion
from devotional_content import daily_lectionary_page
from devotional_content import extended_evening
from devotional_content import gospels_by_category
from devotional_content import lent
from devotional_content import liturgical_calendar
from devotional_content import memory
from devotional_content import mid_week
from devotional_content import new_year
from devotional_content import nicene_creed_study
from devotional_content import prayer_weaver
from devotional_content import psalms_by_category
from devotional_content import short_prayers
from devotional_content import small_catechism
from devotional_content import trinity_study
from firebase_admin import auth as firebase_admin_auth
import flask
from flask_compress import Compress
import flask_login
from google.cloud import firestore
import liturgy
import menu
import models
import pytz
import requests
import secrets_fetcher
import streak_logic
from services import analytics_ga4
from services import fullofeyes_scraper
from services import prayer_requests
from services import reminders
from services import users
from twilio.request_validator import RequestValidator
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

# Gzip/Brotli-compress text responses (HTML, CSS, JS, JSON) to cut transfer size.
Compress(app)

app.secret_key = secrets_fetcher.get_flask_secret_key()
app.config["PREFERRED_URL_SCHEME"] = "https"
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=31)
app.config["REMEMBER_COOKIE_DURATION"] = datetime.timedelta(days=31)
app.config["SESSION_COOKIE_SECURE"] = True
# SameSite=Lax: closes the CSRF vector on the form routes (the session cookie no
# longer rides cross-site POSTs). The earlier "Lax broke sign-in" result was
# confounded -- that break was X-Frame-Options + a cross-origin authDomain (now
# fixed; see Fable_audit.md items 5 and 19), not the cookie. Firebase sign-in is
# same-origin, so Lax should not affect it. Verify Google sign-in on staging
# before promoting to prod.
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["REMEMBER_COOKIE_SECURE"] = True
app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
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


@app.before_request
def redirect_www_to_apex():
  """Canonicalizes www.* to the bare apex so Google sign-in stays same-origin.

  Firebase runs its sign-in auth helper on authDomain=asimplewaytopray.com (the
  apex; see /auth/firebase_config). On a www page that auth-helper iframe is
  cross-origin, and X-Frame-Options: SAMEORIGIN refuses to frame it -- so
  signInWithPopup finishes the Google step but can never relay the result back
  to the opener, and the popup just closes without signing the user in. Forcing
  every request onto the apex keeps the page, its authDomain, and the proxied
  /__/auth helper all on one origin. (staging.asimplewaytopray.com has no www.
  prefix, so it is unaffected and self-references per fe2e931.)
  """
  host = flask.request.host
  if host.startswith("www."):
    apex = host[len("www."):]
    target = f"{flask.request.scheme}://{apex}{flask.request.path}"
    query = flask.request.query_string.decode("utf-8")
    if query:
      target += f"?{query}"
    return flask.redirect(target, code=301)


@app.before_request
def track_last_seen():
  """Records when an authenticated user was last active.

  Throttled to at most one Firestore write per user every 10 minutes, using
  the already-loaded current_user.last_seen so no extra read is needed.
  """
  if flask.request.endpoint == "static":
    return
  if not flask_login.current_user.is_authenticated:
    return

  now = datetime.datetime.now(datetime.timezone.utc)
  last_seen = getattr(flask_login.current_user, "last_seen", None)
  if isinstance(last_seen, datetime.datetime):
    if last_seen.tzinfo is None:
      last_seen = last_seen.replace(tzinfo=datetime.timezone.utc)
    if now - last_seen < datetime.timedelta(minutes=10):
      return

  try:
    users.update_last_seen(flask_login.current_user.id, now)
  except Exception as e:
    app.logger.error(f"Failed to update last_seen: {e}")


@app.after_request
def set_static_cache_headers(response):
  """Sets cache lifetimes for static assets.

  Static files get a long max-age so repeat visits avoid re-downloading them
  (styles.css is busted by the ?v= query string when it changes). The service
  worker is kept on no-cache so worker updates ship promptly.
  """
  path = flask.request.path
  if path == "/sw.js":
    response.headers["Cache-Control"] = "no-cache"
  elif flask.request.endpoint == "static" or path.startswith("/static/"):
    response.headers["Cache-Control"] = "public, max-age=604800"  # 7 days
  return response


# Report-Only Content-Security-Policy. It never blocks anything; it reports (to
# /csp-report and the browser console) what an enforced policy would need to
# allow. 'unsafe-inline' is included because the templates use inline scripts
# and styles today, so reports surface unexpected *external* sources rather than
# the known inline usage. External origins are grounded in what the templates
# actually load: GA / Tag Manager, the Firebase SDK (gstatic), Google Fonts,
# d3js, jsDelivr, and the Firebase / Google auth frames.
CSP_REPORT_ONLY = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://www.googletagmanager.com"
    " https://www.gstatic.com https://d3js.org https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com"
    " https://cdn.jsdelivr.net",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https:",
    "connect-src 'self' https://www.google-analytics.com"
    " https://www.googletagmanager.com https://analytics.google.com"
    " https://identitytoolkit.googleapis.com https://securetoken.googleapis.com"
    " https://*.googleapis.com",
    "frame-src 'self' https://*.firebaseapp.com https://accounts.google.com"
    " https://apis.google.com https://docs.google.com",
    "frame-ancestors 'self' https://apis.google.com https://accounts.google.com"
    " https://*.firebaseapp.com",
    "base-uri 'self'",
    "form-action 'self' https://accounts.google.com",
    "report-uri /csp-report",
])


@app.after_request
def set_security_headers(response):
  """Adds defensive security headers to every response.

  CSP is sent in Report-Only mode for now: it never blocks anything, it only
  surfaces (via /csp-report and the browser console) what a future enforced
  policy would need to allow. setdefault is used so an individual route may
  still override any of them.

  X-Frame-Options: SAMEORIGIN is sent. The Firebase sign-in flow works with it
  as long as the auth-helper framing stays SAME-ORIGIN -- which holds when the
  page, its authDomain, and the proxied /__/auth handler are all the same origin
  (each environment self-references via /auth/firebase_config, served fresh and
  uncached). It broke earlier only when staging, using a stale cached config,
  cross-origin-framed the prod authDomain. Prod has always run with this header.
  """
  response.headers.setdefault("X-Content-Type-Options", "nosniff")
  response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
  response.headers.setdefault(
      "Referrer-Policy", "strict-origin-when-cross-origin"
  )
  # HSTS only over HTTPS (ProxyFix derives request.is_secure from
  # X-Forwarded-Proto), so local http development isn't pinned to HTTPS.
  if flask.request.is_secure:
    response.headers.setdefault(
        "Strict-Transport-Security", "max-age=31536000"
    )
  # CSP applies to documents; skip it on static asset (CSS/JS/image) responses.
  if response.mimetype == "text/html":
    response.headers.setdefault(
        "Content-Security-Policy-Report-Only", CSP_REPORT_ONLY
    )
  return response


@app.route("/csp-report", methods=["POST"])
def csp_report_route():
  """Logs Content-Security-Policy violation reports (Report-Only mode).

  Unauthenticated by design -- browsers POST these reports without credentials.
  Kept deliberately minimal: only payloads that look like CSP reports are logged
  (truncated), and it always returns 204.
  """
  body = flask.request.get_data(as_text=True) or ""
  if "violated-directive" in body or "csp-report" in body:
    app.logger.warning("CSP report: %s", body[:2000])
  return ("", 204)


def admin_required(f):
  """Aborts with 403 unless the current user is the configured admin.

  Use below @flask_login.login_required so authentication (and its login
  redirect) is handled first.
  """
  @functools.wraps(f)
  def wrapper(*args, **kwargs):
    admin_id = app.config.get("ADMIN_USER_ID")
    if not admin_id or flask_login.current_user.id != admin_id:
      return flask.abort(403)
    return f(*args, **kwargs)

  return wrapper


@app.context_processor
def inject_globals():
  """Injects global variables into all templates."""
  now = utils.now_for_user(flask_login.current_user)
  is_advent = now.month == 12 and 1 <= now.day <= 25
  is_new_year = (now.month == 12 and now.day == 31) or (
      now.month == 1 and now.day == 1
  )

  cy = liturgy.get_church_year(now.year)
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


@app.errorhandler(404)
def page_not_found(_error):
  """Render a branded 404 page instead of Flask's default."""
  return flask.render_template("404.html"), 404


@app.errorhandler(500)
def internal_server_error(_error):
  """Render a branded 500 page instead of Flask's default."""
  return flask.render_template("500.html"), 500


@app.route("/")
def index_route():
  """Returns the homepage HTML.

  The seasonal flags (is_advent/is_new_year/is_lent) the page needs are already
  supplied to every template by the inject_globals context processor, so the
  route just renders.
  """
  return flask.render_template("index.html")


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
    if (
        user.created_at
        and (
            datetime.datetime.now(datetime.timezone.utc) - user.created_at
        ).total_seconds()
        < 60
    ):
      flask.flash(
          'Welcome! Visit <a href="/settings">Settings</a> to manage'
          " notification preferences.",
          "success",
      )
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
  # Constant-time compare, same as the cron-auth check: a 6-digit code is too
  # short for a practical timing attack, but == leaks match length/prefix.
  if secrets.compare_digest(code, pending_data["code"]):
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
      flask.flash(
          'Account verified and updated! Visit <a href="/settings">Settings</a>'
          " to manage notification preferences.",
          "success",
      )
    else:
      # Create new user
      user_data = {
          "name": pending_data["name"],
          "email": pending_data["email"],
          "password_hash": pending_data["password_hash"],
          "created_at": datetime.datetime.now(datetime.timezone.utc),
      }
      user = users.create_new_user_doc(user_data, "email")
      flask.flash(
          'Account created successfully! Visit <a href="/settings">Settings</a>'
          " to manage notification preferences.",
          "success",
      )

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


@app.route("/auth/firebase_config")
def firebase_auth_config_route():
  """Public Firebase config for the sign-in pages.

  Unlike /firebase_config (login-required, includes the messaging vapidKey),
  this returns only the fields the Firebase JS SDK needs to start a sign-in,
  which must be readable before the user is authenticated. These values are
  public by design in Firebase web apps; access control happens server-side
  via ID-token verification in /auth/firebase.
  """
  try:
    # authDomain must be SAME-ORIGIN with the page running signInWithPopup so
    # the Firebase auth-helper iframe/handler framing stays same-origin --
    # otherwise X-Frame-Options: SAMEORIGIN blocks it. Prod (asimplewaytopray.com)
    # is naturally same-origin; staging must self-reference, because framing the
    # prod authDomain from staging is cross-origin and gets refused. Each host
    # used here must be a Firebase "Authorized domain" AND have its
    # /__/auth/handler registered as an OAuth redirect URI.
    auth_domain = "asimplewaytopray.com"
    if flask.request.host == "staging.asimplewaytopray.com":
      auth_domain = "staging.asimplewaytopray.com"
    return flask.jsonify({
        "apiKey": secrets_fetcher.get_firebase_api_key(),
        # Our own domain, so Google's account chooser says "to continue to
        # <our domain>" rather than the default firebaseapp.com domain.
        # Requires the /__/auth + /__/firebase reverse proxy below and the
        # matching redirect URI on the OAuth client.
        "authDomain": auth_domain,
        "projectId": "lcms-prayer-app",
        "messagingSenderId": secrets_fetcher.get_firebase_messaging_sender_id(),
        "appId": secrets_fetcher.get_firebase_app_id(),
    })
  except Exception as e:  # pylint: disable=broad-except
    app.logger.error("Failed to fetch Firebase auth config: %s", e)
    return flask.jsonify({"error": "Failed to fetch config"}), 500


# Where the Firebase-hosted auth helper actually lives; the proxy below
# serves it from our domain instead.
_FIREBASE_AUTH_HELPER_ORIGIN = "https://lcms-prayer-app.firebaseapp.com"

# Hop-by-hop (and encoding) headers that must not be forwarded verbatim:
# requests has already decoded the body, and the WSGI server sets framing.
_PROXY_SKIP_HEADERS = frozenset({
    "connection",
    "content-encoding",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
})


@app.route("/__/auth/<path:_subpath>", methods=["GET", "POST"])
@app.route("/__/firebase/<path:_subpath>", methods=["GET", "POST"])
def firebase_auth_helper_proxy(_subpath):
  """Reverse-proxies the Firebase Auth helper pages onto our domain.

  This lets the sign-in flow use authDomain=asimplewaytopray.com: the
  sign-in popup opens /__/auth/handler on OUR origin (the helper also
  fetches /__/firebase/init.json), so the OAuth redirect -- and therefore
  the domain Google displays on its account chooser -- is our domain. The
  helper content itself still comes from Firebase; this is the reverse-proxy
  setup Firebase's own auth docs describe for custom auth domains.
  """
  upstream = _FIREBASE_AUTH_HELPER_ORIGIN + flask.request.path
  if flask.request.query_string:
    upstream += "?" + flask.request.query_string.decode("utf-8")

  request_headers = {}
  if flask.request.content_type:
    request_headers["Content-Type"] = flask.request.content_type

  try:
    upstream_resp = requests.request(
        flask.request.method,
        upstream,
        headers=request_headers,
        data=(
            flask.request.get_data()
            if flask.request.method == "POST"
            else None
        ),
        timeout=15,
        allow_redirects=False,  # Pass 3xx through so the browser follows it.
    )
  except requests.RequestException as e:
    app.logger.error("Firebase auth helper proxy failed: %s", e)
    return "Authentication service unavailable.", 502

  headers = [
      (name, value)
      for name, value in upstream_resp.headers.items()
      if name.lower() not in _PROXY_SKIP_HEADERS
  ]
  return flask.Response(
      upstream_resp.content, status=upstream_resp.status_code, headers=headers
  )


@app.route("/auth/firebase", methods=["POST"])
def firebase_auth_route():
  """Session bridge for Firebase Authentication.

  Verifies a Firebase ID token (sent by a web client or a native app shell,
  where Google's OAuth pages are blocked inside webviews) and establishes the
  same Flask-Login session that the legacy flows create, so every existing
  @login_required route keeps working unchanged. Coexists with -- does not
  replace -- the legacy Google-OAuth and email/password routes.
  """
  data = flask.request.get_json(silent=True) or {}
  id_token = data.get("idToken")
  if not id_token or not isinstance(id_token, str):
    return flask.jsonify({"success": False, "error": "Missing idToken"}), 400

  try:
    # firebase_admin is initialized at import time in communication.py.
    claims = firebase_admin_auth.verify_id_token(id_token)
  except Exception as e:  # pylint: disable=broad-except
    app.logger.warning("Firebase ID token verification failed: %s", e)
    return flask.jsonify({"success": False, "error": "Invalid token"}), 401

  user, error = users.handle_firebase_login(claims)
  if user is None:
    code, message = error
    status = {
        "invalid_token": 401,
        "email_unverified": 403,
        "unverified_email_conflict": 409,
    }.get(code, 400)
    return (
        flask.jsonify({"success": False, "error": message, "code": code}),
        status,
    )

  flask_login.login_user(user, remember=True)
  flask.session.permanent = True
  return flask.jsonify({"success": True})


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
    return flask.render_template(
        "prayer_completed.html",
        message=result.get("message", "Prayer recorded!"),
        streak=result.get("streak", 0),
    )
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

  flask.flash(
      'Accounts linked successfully! Visit <a href="/settings">Settings</a> to'
      " manage notification preferences.",
      "success",
  )
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
def morning_devotion_route_old():
  """Redirects old morning devotion URL to new one."""
  return flask.redirect(
      flask.url_for("office_devotion_route", office_name="morning")
  )


@app.route("/midday_devotion")
def midday_devotion_route_old():
  """Redirects old midday devotion URL to new one."""
  return flask.redirect(
      flask.url_for("office_devotion_route", office_name="midday")
  )


@app.route("/evening_devotion")
def evening_devotion_route_old():
  """Redirects old evening devotion URL to new one."""
  return flask.redirect(
      flask.url_for("office_devotion_route", office_name="evening")
  )


@app.route("/close_of_day_devotion")
def close_of_day_devotion_route_old():
  """Redirects old close of day devotion URL to new one."""
  return flask.redirect(
      flask.url_for("office_devotion_route", office_name="close_of_day")
  )


@app.route("/night_watch_devotion")
def night_watch_devotion_route_old():
  """Redirects old night watch devotion URL to new one."""
  return flask.redirect(
      flask.url_for("office_devotion_route", office_name="night_watch")
  )


@app.route("/office/<string:office_name>")
def office_devotion_route(office_name):
  """Returns the generated devotion HTML for morning, midday, evening, etc."""
  offices = {"morning", "midday", "evening", "close_of_day", "night_watch"}
  if office_name not in offices:
    flask.abort(404)
  user_id = (
      flask_login.current_user.id
      if flask_login.current_user.is_authenticated
      else None
  )
  date_obj = get_date_from_request()
  template_data = utils.get_office_devotion_data(user_id, office_name, date_obj)
  return flask.render_template(f"{office_name}_devotion.html", **template_data)


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


@app.route("/prayer_requests")
@flask_login.login_required
def prayer_requests_route():
  """Renders the prayer requests page."""
  return flask.render_template("prayer_requests.html")


@app.route("/prayer_weaver")
def prayer_weaver_route():
  """Renders the Prayer Weaver tool."""
  return prayer_weaver.render_prayer_weaver_page()


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


@app.route("/catechism_memory")
def catechism_memory_route():
  """Returns Catechism Memorization page."""
  return catechism_memory.generate_catechism_memory_page()


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


@app.route("/trinity_study")
def trinity_study_route():
  """Returns Trinity Study page."""
  return trinity_study.generate_trinity_study_page()


@app.route("/bible_family_tree")
def bible_family_tree_route():
  """Returns the interactive Bible Family Tree page."""
  return flask.render_template("bible_family_tree.html")


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
    # The user document is already loaded onto current_user by the Flask-Login
    # user_loader, so read from it instead of issuing a second Firestore get.
    bia_progress = flask_login.current_user.bia_progress
    completed_days = flask_login.current_user.completed_bible_days
    bible_streak = flask_login.current_user.bible_streak_count

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
  answered_requests = prayer_requests.get_answered_prayer_requests(limit=10)
  prayed_request_ids = []
  if flask_login.current_user.is_authenticated:
    db = utils.get_db_client()
    user_doc_ref = db.collection("users").document(flask_login.current_user.id)
    user_doc = user_doc_ref.get()
    if user_doc.exists:
      prayed_request_ids = user_doc.to_dict().get("prayed_request_ids", [])
      if prayed_request_ids:
        prayer_requests_ref = db.collection("prayer-requests")
        refs = [
            prayer_requests_ref.document(rid) for rid in prayed_request_ids
        ]
        existing_ids = {snap.id for snap in db.get_all(refs) if snap.exists}
        active_prayed_request_ids = [
            rid for rid in prayed_request_ids if rid in existing_ids
        ]

        if len(active_prayed_request_ids) < len(prayed_request_ids):
          user_doc_ref.update({"prayed_request_ids": active_prayed_request_ids})
          prayed_request_ids = active_prayed_request_ids

  return flask.render_template(
      "prayer_wall.html",
      prayer_requests=active_requests,
      answered_requests=answered_requests,
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


def _save_user_fields(updates, use_merge=True):
  """Writes fields to the current user's doc and returns a JSON response.

  use_merge=True creates the doc if absent (set with merge); use_merge=False
  uses update(), which is required for dotted nested-field keys.
  """
  try:
    db = utils.get_db_client()
    user_ref = db.collection("users").document(flask_login.current_user.id)
    if use_merge:
      user_ref.set(updates, merge=True)
    else:
      user_ref.update(updates)
    return flask.jsonify({"success": True})
  except Exception as e:
    app.logger.error("Failed to save user setting %s: %s", list(updates), e)
    return (
        flask.jsonify({"success": False, "error": "Database save failed"}),
        500,
    )


@app.route("/save_dark_mode", methods=["POST"])
@flask_login.login_required
def save_dark_mode_route():
  """Saves dark mode preference for the current user."""
  value = flask.request.json.get("dark_mode")
  if not isinstance(value, bool):
    return flask.jsonify({"success": False, "error": "Invalid data"}), 400
  return _save_user_fields({"dark_mode": value})


@app.route("/save_background_art", methods=["POST"])
@flask_login.login_required
def save_background_art_route():
  """Saves background art preference for the current user."""
  value = flask.request.json.get("background_art")
  if not isinstance(value, bool):
    return flask.jsonify({"success": False, "error": "Invalid data"}), 400
  return _save_user_fields({"background_art": value})


@app.route("/save_hide_catechism", methods=["POST"])
@flask_login.login_required
def save_hide_catechism_route():
  """Saves the hide-catechism preference for the current user."""
  value = flask.request.json.get("hide_catechism")
  if not isinstance(value, bool):
    return flask.jsonify({"success": False, "error": "Invalid data"}), 400
  return _save_user_fields({"hide_catechism": value})


@app.route("/save_font_size", methods=["POST"])
@flask_login.login_required
def save_font_size_route():
  """Saves font size preference for the current user."""
  value = flask.request.json.get("font_size_level")
  if not isinstance(value, int):
    return flask.jsonify({"success": False, "error": "Invalid data"}), 400
  return _save_user_fields({"font_size_level": value})


@app.route("/api/save_reading_preference", methods=["POST"])
@flask_login.login_required
def save_reading_preference_route():
  """Saves reading preference for a specific devotion."""
  data = flask.request.json
  devotion = data.get("devotion")
  preference = data.get("preference")

  if not devotion or not preference:
    return flask.jsonify({"success": False, "error": "Missing fields"}), 400

  return _save_user_fields(
      {f"reading_preferences.{devotion}": preference}, use_merge=False
  )


@app.route("/api/save_psalm_preference", methods=["POST"])
@flask_login.login_required
def save_psalm_preference_route():
  """Saves psalm preference for a specific devotion."""
  data = flask.request.json
  devotion = data.get("devotion")
  preference = data.get("preference")

  if not devotion or not preference:
    return flask.jsonify({"success": False, "error": "Missing fields"}), 400

  return _save_user_fields(
      {f"psalm_preferences.{devotion}": preference}, use_merge=False
  )


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
  answered_prayers = []

  if flask_login.current_user.is_authenticated:
    try:
      raw_prayers = utils.fetch_personal_prayers(flask_login.current_user.id)
      for prayer in raw_prayers:
        if prayer.get("category") not in prayers_by_cat:
          continue
        prayer["text"] = utils.decrypt_text(prayer["text"])
        if prayer.get("for_whom"):
          prayer["for_whom"] = utils.decrypt_text(prayer["for_whom"])
        if prayer.get("answered"):
          answered_prayers.append(prayer)
        else:
          prayers_by_cat[prayer["category"]].append(prayer)
    except Exception as e:
      app.logger.error("Failed to fetch personal prayers: %s", e)
      flask.flash("Could not load personal prayers.", "error")

  # Most recently answered first; tolerate legacy docs without a timestamp.
  epoch = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
  answered_prayers.sort(
      key=lambda p: p.get("answered_at") or epoch, reverse=True
  )

  return flask.render_template(
      "my_prayers.html",
      prayers_by_cat=prayers_by_cat,
      categories=categories,
      answered_prayers=answered_prayers,
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
  category_count = sum(
      1
      for _ in db.collection("users")
      .document(flask_login.current_user.id)
      .collection("personal-prayers")
      .where("category", "==", category)
      .stream()
  )
  data = {
      "user_id": flask_login.current_user.id,
      "category": category,
      "text": utils.encrypt_text(prayer_text),
      "position": category_count,
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

  if doc.to_dict().get("category") != category:
    new_category_count = sum(
        1
        for _ in db.collection("users")
        .document(user_id)
        .collection("personal-prayers")
        .where("category", "==", category)
        .stream()
    )
    update_data["position"] = new_category_count

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


@app.route("/move_personal_prayer", methods=["POST"])
@flask_login.login_required
def move_personal_prayer_route():
  """Moves a personal prayer up or down within its category."""
  prayer_id = flask.request.form.get("prayer_id")
  direction = flask.request.form.get("direction")
  if not prayer_id or direction not in ("up", "down"):
    flask.flash("Invalid move request.", "error")
    return flask.redirect(flask.url_for("my_prayers_route"))

  db = utils.get_db_client()
  user_id = flask_login.current_user.id
  collection_ref = (
      db.collection("users").document(user_id).collection("personal-prayers")
  )
  doc_ref = collection_ref.document(prayer_id)
  doc = doc_ref.get()
  if not doc.exists or doc.to_dict().get("user_id") != user_id:
    flask.flash("Prayer not found or permission denied.", "error")
    return flask.redirect(flask.url_for("my_prayers_route"))

  category = doc.to_dict().get("category")
  if not category:
    return flask.redirect(flask.url_for("my_prayers_route"))

  # Read all prayers in this category and normalize positions so we can swap
  # with a neighbor even if some legacy prayers don't yet have a position.
  siblings = []
  for sib in collection_ref.where("category", "==", category).stream():
    siblings.append({"id": sib.id, "data": sib.to_dict()})
  siblings.sort(key=lambda s: utils._personal_prayer_sort_key(s["data"]))

  idx = next((i for i, s in enumerate(siblings) if s["id"] == prayer_id), None)
  if idx is None:
    return flask.redirect(flask.url_for("my_prayers_route"))

  target = idx - 1 if direction == "up" else idx + 1
  if target < 0 or target >= len(siblings):
    return flask.redirect(flask.url_for("my_prayers_route"))

  siblings[idx], siblings[target] = siblings[target], siblings[idx]

  batch = db.batch()
  for new_pos, sib in enumerate(siblings):
    if sib["data"].get("position") != new_pos:
      batch.update(collection_ref.document(sib["id"]), {"position": new_pos})
  batch.commit()

  return flask.redirect(flask.url_for("my_prayers_route"))


@app.route("/mark_personal_prayer_answered", methods=["POST"])
@flask_login.login_required
def mark_personal_prayer_answered_route():
  """Marks a personal prayer as answered, or restores it to the active list."""
  prayer_id = flask.request.form.get("prayer_id")
  answered = flask.request.form.get("answered") == "true"
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
  if not doc.exists or doc.to_dict().get("user_id") != user_id:
    flask.flash("Prayer not found or permission denied.", "error")
    return flask.redirect(flask.url_for("my_prayers_route"))

  if answered:
    doc_ref.update({
        "answered": True,
        "answered_at": datetime.datetime.now(datetime.timezone.utc),
    })
  else:
    doc_ref.update({
        "answered": False,
        "answered_at": firestore.DELETE_FIELD,
    })
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
  except Exception as e:  # pylint: disable=broad-except
    app.logger.warning("Memory-verse ref validation failed for %r: %s", ref, e)
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


@app.route("/mark_prayer_answered/<request_id>", methods=["POST"])
@flask_login.login_required
def mark_prayer_answered_route(request_id):
  """Marks the current user's prayer request as answered (a praise report)."""
  data = flask.request.json or {}
  testimony = data.get("testimony")

  success, error_message = prayer_requests.mark_prayer_answered(
      request_id, flask_login.current_user.id, testimony
  )
  if success:
    return flask.jsonify({"success": True})
  return flask.jsonify({"success": False, "error": error_message}), 400


@app.route("/api/random_prayer_request")
def random_prayer_request_route():
  """Returns a random active prayer request."""
  exclude_user_id = None
  if flask_login.current_user.is_authenticated:
    exclude_user_id = flask_login.current_user.id

  prayer = prayer_requests.get_random_prayer_request(
      exclude_user_id=exclude_user_id
  )
  if prayer:
    return flask.jsonify({"success": True, "prayer": prayer})
  else:
    return flask.jsonify({
        "success": False,
        "message": "No active prayer requests found.",
    })


@app.route("/admin/traffic")
@flask_login.login_required
@admin_required
def admin_traffic_route():
  """Renders the GA4 traffic analytics page."""
  # Fetch registered users from Firestore
  registered_users = []
  streak_users = []
  registered_user_count = 0
  try:
    db = utils.get_db_client()
    users_ref = db.collection("users")
    # Fetch all users
    docs = users_ref.stream()

    eastern_timezone = utils.EASTERN_TZ

    for doc in docs:
      data = doc.to_dict()

      # Prefer activity-based "last seen"; fall back to last_login for users
      # who haven't been active since last_seen tracking began.
      last_seen = data.get("last_seen") or data.get("last_login")
      last_seen_val = datetime.datetime.min.replace(
          tzinfo=datetime.timezone.utc
      )
      last_seen_str = "Never"

      if last_seen:
        if isinstance(last_seen, datetime.datetime):
          # Ensure aware
          if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=datetime.timezone.utc)
          last_seen_est = last_seen.astimezone(eastern_timezone)
          last_seen_str = last_seen_est.strftime("%Y-%m-%d %I:%M %p")
          last_seen_val = last_seen
        else:
          last_seen_str = str(last_seen)

      registered_users.append({
          "name": data.get("name", "Unknown"),
          "email": data.get("email", "Unknown"),
          "last_seen": last_seen_str,
          # Migrated to Firebase Auth (signed in through /auth/firebase at
          # least once, which links this field).
          "firebase_linked": bool(data.get("firebase_uid")),
          "_sort_key": last_seen_val,
      })

      # Build the active-streaks list: users whose prayer streak is still
      # alive (prayed today or yesterday in their timezone).
      tz_str = data.get("timezone")
      active_streak = models.compute_active_streak(
          data.get("streak_count", 0), data.get("last_prayer_date"), tz_str
      )
      if active_streak >= 1:
        streak_users.append({
            "name": data.get("name", "Unknown"),
            "streak": active_streak,
            "best_streak": max(data.get("best_streak_count", 0), active_streak),
            "bible_streak": models.compute_active_streak(
                data.get("bible_streak_count", 0),
                data.get("last_bible_reading_date"),
                tz_str,
            ),
        })

    # Sort users by last seen (desc) and streaks by current streak (desc).
    registered_users.sort(key=lambda x: x["_sort_key"], reverse=True)
    streak_users.sort(key=lambda x: x["streak"], reverse=True)
    registered_user_count = len(registered_users)

  except Exception as e:
    app.logger.error(f"Error fetching users: {e}")

  firebase_linked_count = sum(
      1 for u in registered_users if u["firebase_linked"]
  )

  try:
    property_id = secrets_fetcher.get_ga4_property_id()
    data = analytics_ga4.fetch_traffic_stats(property_id)
    data["registered_user_count"] = registered_user_count
    data["registered_users"] = registered_users
    data["streak_users"] = streak_users
    data["firebase_linked_count"] = firebase_linked_count
    return flask.render_template("admin_traffic.html", **data)
  except Exception as e:
    # If fetch fails (e.g. secret not set), return error info
    return flask.render_template(
        "admin_traffic.html",
        error=str(e),
        service_email=analytics_ga4.get_service_account_email(),
        registered_user_count=registered_user_count,
        registered_users=registered_users,
        streak_users=streak_users,
        firebase_linked_count=firebase_linked_count,
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
      data.get("timezone"),
      data.get("reading_type"),
      data.get("psalm_type"),
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


def _is_authorized_task_request():
  """Returns True if the caller is an authorized cron/task invoker.

  Accepts the App Engine / Cloud Scheduler cron header (which Google strips from
  external requests) or a shared secret in X-Tasks-Secret matching TASKS_SECRET.
  When TASKS_SECRET is unset the endpoint stays open (its prior behavior) but
  logs a warning, so deploying this change doesn't break an existing scheduler
  before the secret and the scheduler's header are wired up.
  """
  if flask.request.headers.get("X-Appengine-Cron") == "true":
    return True
  expected = secrets_fetcher.get_tasks_secret()
  if not expected:
    app.logger.warning(
        "/tasks/send_reminders invoked without TASKS_SECRET configured;"
        " allowing unauthenticated. Set TASKS_SECRET to enforce."
    )
    return True
  provided = flask.request.headers.get("X-Tasks-Secret", "")
  if secrets.compare_digest(provided, expected):
    return True
  app.logger.warning(
      "Rejected /tasks/send_reminders: missing or invalid X-Tasks-Secret."
  )
  return False


@app.route("/tasks/send_reminders")
def send_reminders_task():
  """Cron task to send due reminders."""
  if not _is_authorized_task_request():
    return flask.abort(403)
  reminders.send_due_reminders()
  return "OK", 200


@app.route("/debug/force_reminders", methods=["POST"])
@flask_login.login_required
@admin_required
def force_reminders_route():
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

  catechism_total = len(utils.get_catechism_sections())
  catechism_completed = len(user.completed_catechism_sections)
  catechism_pct = 0
  if catechism_total > 0:
    catechism_pct = int((catechism_completed / catechism_total) * 100)

  # Today (in the user's timezone) drives the "prayed/read today" flags and the
  # time-of-day devotion recommendation below.
  now = utils.now_for_user(user)
  today_str = now.strftime("%Y-%m-%d")
  prayed_today = user.last_prayer_date == today_str

  # Whether a grace day is currently available to protect the prayer streak.
  prayer_grace_available = streak_logic.grace_available(
      streak_logic.parse_ymd(user.last_prayer_grace_date), now.date()
  )

  # Determine if read bible today
  read_bible_today = user.last_bible_reading_date == today_str

  # Count devotions today
  devotions_today_count = 0
  if user.completed_devotions:
    for ts_str in user.completed_devotions.values():
      if ts_str.startswith(today_str):
        devotions_today_count += 1

  # Determine recommended devotion
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
      prayer_grace_available=prayer_grace_available,
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
  # Reject forged webhooks. Twilio signs every request with the account auth
  # token over the full URL + POST params, so verifying X-Twilio-Signature stops
  # a spoofed STOP from disabling someone's SMS. If the token isn't configured
  # (e.g. a non-prod environment) validation is skipped with a warning.
  auth_token = secrets_fetcher.get_twilio_api_key()
  if auth_token:
    validator = RequestValidator(auth_token)
    signature = flask.request.headers.get("X-Twilio-Signature", "")
    if not validator.validate(
        flask.request.url, flask.request.form, signature
    ):
      app.logger.warning(
          "Rejected Twilio webhook with invalid signature (url=%s)",
          flask.request.url,
      )
      return flask.abort(403)
  else:
    app.logger.warning(
        "Twilio auth token not configured; skipping webhook signature check."
    )

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
