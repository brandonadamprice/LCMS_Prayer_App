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
  if "Ash Wednesday" in key or "Lent" in key:
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
      try:
        # If key is just a date, maybe look up special feasts?
        # The get_liturgical_key handles moveable feasts.
        # Fixed feasts are in lectionary.json keys sometimes, but get_liturgical_key
        # falls back to date string if not in movable season.
        pass
      except:
        pass

      color = get_liturgical_color(key, day, day_cy)
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
