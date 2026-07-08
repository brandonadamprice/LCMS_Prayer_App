"""Functions for generating the mid-week devotion."""

import datetime
import logging

import flask
import flask_login
import utils

logger = logging.getLogger(__name__)


def generate_mid_week_devotion(date_obj=None):
  """Generates HTML for the mid-week devotion."""
  eastern_timezone = utils.EASTERN_TZ
  now = date_obj or datetime.datetime.now(eastern_timezone)
  reading_data = utils.get_mid_week_reading_for_date(now)

  if not reading_data:
    return flask.render_template(
        "prayer_request_failed.html",
        error_message="Mid-week reading data not available for this week.",
    )

  catechism_data = utils.get_catechism_for_day(
      now, rotation="weekly", hidden=utils.catechism_hidden_for_user()
  )

  refs_to_fetch = [
      reading_data["Psalm"],
      reading_data["OT"],
      reading_data["NT Lesson (Epistle)"],
      reading_data["NT Lesson (Gospel)"],
  ]
  try:
    psalm_text, ot_text, epistle_text, gospel_text = utils.fetch_passages(
        refs_to_fetch
    )
  except Exception as e:
    logger.error(f"Error fetching passages for mid-week devotion: {e}")
    return flask.render_template(
        "prayer_request_failed.html",
        error_message="Failed to fetch scripture passages.",
    )

  personal_prayers_by_topic = {}
  if flask_login.current_user.is_authenticated:
    try:
      personal_prayers_by_topic = utils.get_all_personal_prayers_for_user()
    except Exception as e:
      logger.error(f"Error fetching personal prayers for mid-week: {e}")

  weekly_prayers_list = []
  for i in range(7):
    prayer_data = utils.WEEKLY_PRAYERS[str(i)].copy()
    topic = prayer_data["topic"]
    prayer_data["personal_prayers"] = personal_prayers_by_topic.get(topic, [])
    weekly_prayers_list.append(prayer_data)

  prev_date, next_date = utils.devotion_nav_dates(now)

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "prev_date": prev_date,
      "next_date": next_date,
      "church_season_day": reading_data["church_season_day"],
      "psalm_ref": reading_data["Psalm"],
      "ot_ref": reading_data["OT"],
      "epistle_ref": reading_data["NT Lesson (Epistle)"],
      "gospel_ref": reading_data["NT Lesson (Gospel)"],
      "psalm_text": psalm_text,
      "ot_text": ot_text,
      "epistle_text": epistle_text,
      "gospel_text": gospel_text,
      "weekly_prayers_list": weekly_prayers_list,
      "mid_week_prayer": reading_data["Prayer"],
  }
  template_data.update(catechism_data)

  return flask.render_template("mid_week_devotion.html", **template_data)
