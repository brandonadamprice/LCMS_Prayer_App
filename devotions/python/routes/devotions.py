"""Devotion, study, and memorization content routes."""

import datetime

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
from devotional_content import psalms_by_category
from devotional_content import short_prayers
from devotional_content import small_catechism
from devotional_content import trinity_study
import flask
import flask_login
import utils


def get_date_from_request():
  """Parses 'date' query parameter."""
  date_str = flask.request.args.get("date")
  if date_str:
    try:
      return datetime.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
      pass
  return None


def register(app):
  """Registers the devotional content routes on the app."""

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
