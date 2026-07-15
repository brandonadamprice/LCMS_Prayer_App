"""Personal-prayer, prayer-wall, and prayer-request routes."""

import datetime

from devotional_content import prayer_weaver
import flask
import flask_login
from google.cloud import firestore
from services import prayer_requests
from services import reminders
from services import users
import utils


def register(app, *, rate_limited):
  """Registers the prayer routes on the app."""

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


  @app.route("/prayer_requests")
  @flask_login.login_required
  def prayer_requests_route():
    """Renders the prayer requests page."""
    return flask.render_template("prayer_requests.html")


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


  @app.route("/update_pray_count", methods=["POST"])
  # Unauthenticated Firestore write per POST. Praying through the wall is one
  # click per request and groups do it together on shared wifi, so the cap is
  # deliberately liberal (~1 write/s average per IP) -- it only clips
  # scripted count-stuffing, never a roomful of users.
  @rate_limited("update_pray_count", 600, 600)
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


  @app.route("/prayer_weaver")
  def prayer_weaver_route():
    """Renders the Prayer Weaver tool."""
    return prayer_weaver.render_prayer_weaver_page()
