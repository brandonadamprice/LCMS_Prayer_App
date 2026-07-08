"""Main Flask application for serving devotions."""

import datetime
import functools
import logging
import os

from authlib.integrations.flask_client import OAuth
import flask
from flask_compress import Compress
import flask_login
import liturgy
import menu
import models
import secrets_fetcher
from services import users
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
  if flask.request.path == "/health":
    return  # Health probes would drown out real traffic in the logs.
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


# Route handlers live in the routes/ package. The modules are imported at
# the end -- after the app, its config, the OAuth client, and the decorators
# above exist -- and attach their handlers with plain @app.route calls (not
# Blueprints), so every endpoint name stays exactly as the templates'
# url_for() calls expect.
from routes import api as api_routes  # noqa: E402
from routes import auth as auth_routes  # noqa: E402
from routes import devotions as devotions_routes  # noqa: E402
from routes import misc as misc_routes  # noqa: E402
from routes import prayers as prayers_routes  # noqa: E402
from routes import settings as settings_routes  # noqa: E402

auth_routes.register(app, google=google)
settings_routes.register(app)
devotions_routes.register(app)
prayers_routes.register(app)
api_routes.register(app, admin_required=admin_required)
misc_routes.register(app, admin_required=admin_required)


if __name__ == "__main__":
  app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
