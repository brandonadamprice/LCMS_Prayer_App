"""Functions for generating the Liturgical Calendar page."""

import calendar
import datetime
import flask
import pytz
import utils


def get_liturgical_color(key, date, church_year):
  """Determines the liturgical color based on the day key and date."""
  # Special Days have specific colors
  if (
      "Christmas" in key
      or "Epiphany of Our Lord" in key
      or "All Saints" in key
      or "Trinity" in key
  ):
    return "White"
  if "Ash Wednesday" in key:
    return "Black"
  if "Ash" in key or "Lent" in key:
    return "Violet"
  if "Good Friday" in key:
    return "Black"
  if (
      "Palm Sunday" in key
      or "Pentecost" in key
      or "Reformation" in key
      or "Martyr" in key
      or "Andrew" in key
      or "Thomas" in key
      or "James" in key
      or "Simon" in key
      or "Jude" in key
      or "Matthew" in key
      or "Luke" in key
      or "Mark" in key
      or "Peter" in key
      or "Paul" in key
      or "Bartholomew" in key
      or "Philip" in key
  ):
    return "Red"
  if "Easter" in key or "Ascension" in key:
    return "White"

  # Seasons by date ranges if key is generic or fixed date
  # Advent
  advent_start = church_year.calculate_advent1(date.year)
  if date >= advent_start and date <= datetime.date(date.year, 12, 24):
    advent3 = advent_start + datetime.timedelta(days=14)
    if date == advent3:
      return "Rose"
    return "Violet"

  # Christmas Season (Dec 25 - Jan 5)
  if (date.month == 12 and date.day >= 25) or (
      date.month == 1 and date.day <= 5
  ):
    return "White"

  # Epiphany Season (Jan 6 - Transfiguration)
  # Transfiguration is usually the last Sunday before Lent
  if (
      date >= datetime.date(date.year, 1, 6)
      and date < church_year.ash_wednesday
  ):
    # Transfiguration Sunday is White
    if date == church_year.ash_wednesday - datetime.timedelta(days=3):
      return "White"
    return "Green"

  # Sundays after Pentecost (Trinity Season)
  if date > church_year.holy_trinity and date < advent_start:
    return "Green"

  return "Green"  # Default


def get_season_name(key, date, church_year):
  """Determines the liturgical season."""
  if "Advent" in key:
    return "Advent"
  if "Christmas" in key:
    return "Christmas"
  if "Epiphany" in key:
    return "Epiphany"
  if "Lent" in key or "Ash" in key:
    return "Lent"
  if "Easter" in key:
    return "Easter"
  if "Pentecost" in key:
    return "Pentecost"
  if "Trinity" in key:
    return "Holy Trinity"

  advent_start = church_year.calculate_advent1(date.year)
  if date >= advent_start:
    return "Advent"

  if (date.month == 12 and date.day >= 25) or (
      date.month == 1 and date.day <= 5
  ):
    return "Christmas"

  if (
      date >= datetime.date(date.year, 1, 6)
      and date < church_year.ash_wednesday
  ):
    return "Epiphany"

  if date > church_year.holy_trinity:
    return "Season after Pentecost (Ordinary Time)"

  return "Ordinary Time"


def generate_calendar_data(year, month):
  """Generates calendar data for the given month and year."""
  cal = calendar.Calendar(firstweekday=6)  # Sunday first
  month_days = cal.monthdatescalendar(year, month)

  cy = utils.ChurchYear(year)
  # We might need next year's CY for Dec if Advent starts?
  # Actually ChurchYear class logic handles calculating dates for that year.

  calendar_rows = []
  today = datetime.date.today()

  for week in month_days:
    week_data = []
    for day in week:
      # Note: day might be from prev/next month
      day_cy = utils.ChurchYear(day.year)
      key = day_cy.get_liturgical_key(day)

      # Refine key for display if it is a date string
      display_name = key

      # Suppress "Ash Thursday", "Ash Friday", "Ash Saturday", Pentecost week ferias, and Easter weekdays
      if (
          key
          in [
              "Ash Thursday",
              "Ash Friday",
              "Ash Saturday",
              "Pentecost Monday",
              "Pentecost Tuesday",
              "Pentecost Wednesday",
              "Pentecost Thursday",
              "Pentecost Friday",
              "Pentecost Saturday",
          ]
          or (key.startswith("Easter") and "Sunday" not in key)
          or (key.startswith("Lent") and "Sunday" not in key)
          or (key.startswith("Advent") and "Sunday" not in key)
      ):
        display_name = ""

      # Add names for Advent Sundays and Christmas
      advent1 = day_cy.calculate_advent1(day.year)
      if day == advent1:
        display_name = "Advent 1"
      elif day == advent1 + datetime.timedelta(days=7):
        display_name = "Advent 2"
      elif day == advent1 + datetime.timedelta(days=14):
        display_name = "Advent 3"
      elif day == advent1 + datetime.timedelta(days=21):
        display_name = "Advent 4"

      if day.month == 12 and day.day == 24:
        if display_name == "Advent 4":
          display_name = "Advent 4 / Christmas Eve"
        else:
          display_name = "Christmas Eve"
      elif day.month == 12 and day.day == 25:
        display_name = "Christmas Day"

      try:
        # Fixed feasts are in lectionary.json keys sometimes, but get_liturgical_key
        # falls back to date string if not in movable season.
        date_str_key = day.strftime("%d %b")
        data = utils.load_lectionary(utils.LECTIONARY_JSON_PATH)
        # Check if the key from get_liturgical_key is different from the date string,
        # which means it's a movable feast or already identified.
        # If it IS the date string, we check if there's a special reading for this date
        # that might be a fixed feast (like "St. Mark").
        # Note: The lectionary JSON keys are sometimes dates like "25 Apr" but sometimes
        # names. The current structure of lectionary.json seems to use dates for fixed feasts mostly.
        # However, we can check if the day matches a known fixed feast date manually if needed,
        # or rely on the fact that if get_liturgical_key returned a date string, we might
        # want to check if that date string maps to a special day in a separate mapping if one existed.
        # BUT, looking at the code for get_liturgical_key, it returns "25 Dec" etc.
        # Let's check for specific fixed feasts that might be interesting.

        fixed_feasts = {
            (11, 30): "St. Andrew, Apostle",
            (12, 21): "St. Thomas, Apostle",
            (12, 26): "St. Stephen, Martyr",
            (12, 27): "St. John, Apostle",
            (12, 28): "The Holy Innocents",
            (1, 1): "Circumcision and Name of Jesus",
            (1, 6): "Epiphany of Our Lord",
            (1, 18): "Confession of St. Peter",
            (1, 25): "Conversion of St. Paul",
            (2, 2): "Purification of Mary / Presentation of Our Lord",
            (2, 24): "St. Matthias, Apostle",
            (3, 25): "Annunciation of Our Lord",
            (4, 25): "St. Mark, Evangelist",
            (5, 1): "St. Philip and St. James, Apostles",
            (5, 31): "The Visitation",
            (6, 11): "St. Barnabas, Apostle",
            (6, 24): "Nativity of St. John the Baptist",
            (6, 29): "St. Peter and St. Paul, Apostles",
            (7, 2): "The Visitation (Traditional)",
            (7, 22): "St. Mary Magdalene",
            (7, 25): "St. James the Elder, Apostle",
            (8, 15): "St. Mary, Mother of Our Lord",
            (8, 24): "St. Bartholomew, Apostle",
            (9, 21): "St. Matthew, Apostle",
            (9, 29): "St. Michael and All Angels",
            (10, 18): "St. Luke, Evangelist",
            (10, 28): "St. Simon and St. Jude, Apostles",
            (10, 31): "Reformation Day",
            (11, 1): "All Saints' Day",
        }

        if (day.month, day.day) in fixed_feasts:
          # Only overwrite if it's currently showing a generic date
          if display_name == day.strftime("%d %b"):
            display_name = fixed_feasts[(day.month, day.day)]
          elif (
              display_name == ""
          ):  # Was suppressed
            display_name = fixed_feasts[(day.month, day.day)]
      except:
        pass

      # Use display_name for color if available (e.g. "Reformation Day"),
      # otherwise fallback to key (e.g. "Ash Thursday" which has display_name="")
      color_key = display_name if display_name else key
      color = get_liturgical_color(color_key, day, day_cy)
      season = get_season_name(key, day, day_cy)

      is_today = day == today
      is_current_month = day.month == month

      week_data.append({
          "day": day.day,
          "date_obj": day,
          "key": display_name,
          "color": color.lower(),
          "color_name": color,
          "season": season,
          "is_today": is_today,
          "is_current_month": is_current_month,
      })
    calendar_rows.append(week_data)

  return calendar_rows


def generate_liturgical_calendar_page():
  """Generates HTML for the Liturgical Calendar page."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)

  # Allow query params to change month/year
  try:
    year = int(flask.request.args.get("year", now.year))
    month = int(flask.request.args.get("month", now.month))
  except ValueError:
    year = now.year
    month = now.month

  # Navigation
  prev_month_date = datetime.date(year, month, 1) - datetime.timedelta(days=1)
  next_month_date = datetime.date(year, month, 28) + datetime.timedelta(days=7)
  next_month_date = next_month_date.replace(day=1)

  calendar_data = generate_calendar_data(year, month)

  month_name = calendar.month_name[month]

  template_data = {
      "month_name": month_name,
      "year": year,
      "calendar_data": calendar_data,
      "prev_year": prev_month_date.year,
      "prev_month": prev_month_date.month,
      "next_year": next_month_date.year,
      "next_month": next_month_date.month,
  }

  print("Generated Liturgical Calendar HTML")
  return flask.render_template("liturgical_calendar.html", **template_data)
