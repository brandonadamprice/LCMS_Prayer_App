"""Authentication routes: sign-in, registration, OAuth, and Firebase auth."""

import datetime
import secrets

from firebase_admin import auth as firebase_admin_auth
import flask
import flask_login
import models
import requests
import secrets_fetcher
from services import users
import utils
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash


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


  @app.route("/register", methods=["GET", "POST"])
  @rate_limited("register")
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
  @rate_limited("register_verify")
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
  @rate_limited("email_login")
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
  @rate_limited("forgot_password")
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
