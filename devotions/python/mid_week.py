"""Functions for generating the mid-week devotion."""
import datetime
import flask
import flask_login
import pytz
import utils

def generate_mid_week_devotion():
  """Generates HTML for the mid-week devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  reading_data = utils.get_mid_week_reading_for_date(now)

  if not reading_data:
    return flask.render_template(
        "prayer_request_failed.html",
        error_message="Mid-week reading data not available for this week.",
    )

  catechism_data = utils.get_catechism_for_day(now)

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
    print(f"Error fetching passages for mid-week devotion: {e}")
    return flask.render_template(
        "prayer_request_failed.html",
        error_message="Failed to fetch scripture passages.",
    )

  personal_prayers_by_topic = {}
  if flask_login.current_user.is_authenticated:
    db = utils.get_db_client()
    prayers_ref = db.collection("personal-prayers")
    query = prayers_ref.where("user_id", "==", flask_login.current_user.id)
    try:
      for doc in query.stream():
        prayer = doc.to_dict()
        topic = prayer.get("category")
        if topic:
          if topic not in personal_prayers_by_topic:
            personal_prayers_by_topic[topic] = []
          prayer["text"] = utils.decrypt_text(prayer["text"])
          personal_prayers_by_topic[topic].append(prayer)
    except Exception as e:
      print(f"Error fetching personal prayers for mid-week: {e}")

  weekly_prayers_list = []
  for i in range(7):
    prayer_data = utils.WEEKLY_PRAYERS[str(i)].copy()
    topic = prayer_data["topic"]
    prayer_data["personal_prayers"] = personal_prayers_by_topic.get(topic, [])
    weekly_prayers_list.append(prayer_data)

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
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

  print("Generated Mid-Week Devotion HTML")
  return flask.render_template("mid_week_devotion.html", **template_data)
