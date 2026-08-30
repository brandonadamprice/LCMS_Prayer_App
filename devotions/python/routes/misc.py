"""Public site pages: home, info pages, robots/sitemap, health, admin."""

import datetime

import flask
import flask_login
import models
import secrets_fetcher
from services import analytics_ga4
import signup_analytics_logic
import utils


# Public, evergreen pages worth indexing, with a hint at how often the
# content behind them changes. Account/auth/API routes are deliberately
# absent; robots.txt below also disallows them.
_SITEMAP_PATHS = (
    ("/", "daily"),
    ("/office/morning", "daily"),
    ("/office/midday", "daily"),
    ("/office/evening", "daily"),
    ("/office/close_of_day", "daily"),
    ("/office/night_watch", "daily"),
    ("/extended_evening_devotion", "daily"),
    ("/mid_week_devotion", "daily"),
    ("/childrens_devotion", "daily"),
    ("/advent_devotion", "daily"),
    ("/lent_devotion", "daily"),
    ("/new_year_devotion", "daily"),
    ("/daily_lectionary", "daily"),
    ("/prayer_wall", "daily"),
    ("/bible_in_a_year", "daily"),
    ("/psalter", "daily"),
    ("/litany", "monthly"),
    ("/short_prayers", "monthly"),
    ("/prayer_weaver", "monthly"),
    ("/small_catechism", "monthly"),
    ("/nicene_creed_study", "monthly"),
    ("/trinity_study", "monthly"),
    ("/mary_study", "monthly"),
    ("/bible_family_tree", "monthly"),
    ("/bible_timeline", "monthly"),
    ("/tabernacle", "monthly"),
    ("/church_year_wheel", "monthly"),
    ("/psalms_by_category", "monthly"),
    ("/gospels_by_category", "monthly"),
    ("/memory", "weekly"),
    ("/catechism_memory", "weekly"),
    ("/liturgical_calendar", "weekly"),
    ("/about", "monthly"),
    ("/privacy", "yearly"),
    ("/terms", "yearly"),
    ("/copyright", "yearly"),
)

_ROBOTS_DISALLOW = (
    "/settings",
    "/my_prayers",
    "/reminders",
    "/streaks",
    "/prayer_requests",
    "/admin/",
    "/api/",
    "/auth/",
    "/__/",
    "/login",
    "/logout",
    "/register",
    "/complete_prayer_email/",
    "/tasks/",
    "/debug/",
    "/twilio/",
    "/firebase_config",
    "/get_passage_text",
    "/csp-report",
    "/health",
)


def register(app, *, admin_required):
  """Registers the public/miscellaneous routes on the app."""

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


  @app.route("/.well-known/assetlinks.json")
  def assetlinks_route():
    """Android App Links verification file.

    Lets Android open https://asimplewaytopray.com/... links directly in the
    native app (the manifest's autoVerify intent filter points here). Only
    apps signed with the SHA-256 fingerprints listed in the file are granted
    the association -- see docs/capacitor-android.md for filling those in.
    Android's verifier does not follow redirects, so this must be reachable
    on the apex domain with a direct 200.
    """
    return app.send_static_file("well-known/assetlinks.json")


  @app.route("/health")
  def health_route():
    """Liveness probe for load balancers / uptime monitors.

    Deliberately touches no Firestore or Secret Manager state: it answers "is
    the process serving requests", not "are all dependencies up", so probes
    never add load to (or flap with) the backends.
    """
    return flask.jsonify({"status": "ok"})


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

  @app.route("/terms")
  def terms_route():
    """Returns the terms of service page HTML."""
    return flask.render_template("terms.html")


  @app.route("/robots.txt")
  def robots_txt_route():
    """Crawler directives; staging is kept out of the index entirely."""
    if flask.request.host.startswith("staging."):
      body = "User-agent: *\nDisallow: /\n"
    else:
      lines = ["User-agent: *"]
      lines += [f"Disallow: {path}" for path in _ROBOTS_DISALLOW]
      lines.append(f"Sitemap: https://{flask.request.host}/sitemap.xml")
      body = "\n".join(lines) + "\n"
    return flask.Response(body, mimetype="text/plain")


  @app.route("/sitemap.xml")
  def sitemap_route():
    """XML sitemap of the public content pages."""
    base = "https://" + flask.request.host
    entries = "".join(
        f"<url><loc>{base}{path}</loc><changefreq>{freq}</changefreq></url>"
        for path, freq in _SITEMAP_PATHS
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}</urlset>"
    )
    return flask.Response(xml, mimetype="application/xml")


  @app.route("/admin/traffic")
  @flask_login.login_required
  @admin_required
  def admin_traffic_route():
    """Renders the GA4 traffic analytics page."""
    # Fetch registered users from Firestore
    registered_users = []
    streak_users = []
    registered_user_count = 0
    signup_times = []
    recent_signups = []
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    try:
      db = utils.get_db_client()
      users_ref = db.collection("users")
      # Fetch all users
      docs = users_ref.stream()

      eastern_timezone = utils.EASTERN_TZ

      for doc in docs:
        data = doc.to_dict()

        # Signup analytics. Legacy users created before created_at tracking
        # began return None here and are simply left out of the signup stats
        # (they still appear in the registered-users list below).
        created_at = signup_analytics_logic.as_aware_utc(data.get("created_at"))
        if created_at:
          signup_times.append(created_at)
          if created_at > now_utc - datetime.timedelta(days=30):
            recent_signups.append({
                "name": data.get("name", "Unknown"),
                "email": data.get("email", "Unknown"),
                "firebase_linked": bool(data.get("firebase_uid")),
                "signed_up": created_at.astimezone(eastern_timezone).strftime(
                    "%Y-%m-%d %I:%M %p"
                ),
                "_sort_key": created_at,
            })

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

    # Signup analytics: window counts plus a weekly series for the chart.
    # Pure math, computed even if the Firestore stream failed part-way.
    recent_signups.sort(key=lambda x: x["_sort_key"], reverse=True)
    signup_summary = signup_analytics_logic.summarize_signups(
        signup_times, now_utc
    )
    signup_chart = {
        "labels": [
            w["start"].strftime("%b %d") for w in signup_summary["weekly"]
        ],
        "counts": [w["count"] for w in signup_summary["weekly"]],
    }

    try:
      property_id = secrets_fetcher.get_ga4_property_id()
      data = analytics_ga4.fetch_traffic_stats(property_id)
      data["registered_user_count"] = registered_user_count
      data["registered_users"] = registered_users
      data["streak_users"] = streak_users
      data["firebase_linked_count"] = firebase_linked_count
      data["signup_summary"] = signup_summary
      data["signup_chart"] = signup_chart
      data["recent_signups"] = recent_signups
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
          signup_summary=signup_summary,
          signup_chart=signup_chart,
          recent_signups=recent_signups,
      )
