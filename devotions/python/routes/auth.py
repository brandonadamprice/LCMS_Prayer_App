"""Authentication routes: sign-in, registration, OAuth, and Firebase auth."""

import datetime
import secrets

from firebase_admin import auth as firebase_admin_auth
import flask
import flask_login
import requests
import secrets_fetcher
from services import users
import utils


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


def register(app, *, google, rate_limited):
  """Registers the authentication routes on the app."""

  @app.route("/login")
  def login():
    """Renders the sign-in page."""
    if flask_login.current_user.is_authenticated:
      return flask.redirect("/settings")
    return flask.render_template("signin.html")


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


  @app.route("/register")
  def register():
    """Renders the registration page.

    Sign-up itself happens client-side via Firebase
    (createUserWithEmailAndPassword in _firebase_email_auth.html) and the
    /auth/firebase session bridge; the legacy form-POST flow was removed in
    migration Phase 3b (docs/firebase-auth-migration.md).
    """
    if flask_login.current_user.is_authenticated:
      return flask.redirect("/")
    return flask.render_template("register.html")


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


  @app.route("/__/auth/<path:_subpath>", methods=["GET", "POST"])
  @app.route("/__/firebase/<path:_subpath>", methods=["GET", "POST"])
  # Every hit makes an outbound request (up to 15s) on a worker thread, so
  # this is the site's most abusable endpoint. A real sign-in loads ~a dozen
  # helper resources; 60/min per IP is far above legitimate use.
  @rate_limited("firebase_auth_proxy", 60, 60)
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
  # Firebase throttles credential guessing upstream, but each POST here still
  # costs a token verification plus Firestore lookups. One sign-in = one POST.
  @rate_limited("firebase_session_bridge", 20, 300)
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
