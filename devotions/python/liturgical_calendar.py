"""Functions for generating the Liturgical Calendar page."""

import calendar
import datetime
import json
import flask
import pytz
import utils


def get_liturgical_color(key, date, church_year):
  """Determines the liturgical color based on the day key and date."""
  # Pre-Lent Sundays
  if "Septuagesima" in key or "Sexagesima" in key or "Quinquagesima" in key:
    return "Green"

  # Special Days have specific colors
  # Specific Feast overrides for White
  if (
      "Christmas" in key
      or "Epiphany of Our Lord" in key
      or "All Saints" in key
      or "Trinity" in key
      or "Conversion of St. Paul" in key
      or "Confession of St. Peter" in key
      or "St. John, Apostle" in key
      or "Nativity of St. John the Baptist" in key
      or "Circumcision" in key
      or "Presentation" in key
      or "Annunciation" in key
      or "Visitation" in key
      or "St. Mary" in key
      or "St. Joseph" in key
      or "St. Timothy" in key
      or "St. Titus" in key
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
      or "Holy Cross" in key
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
      or "Barnabas" in key
      or "Matthias" in key
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
  if "Septuagesima" in key or "Sexagesima" in key or "Quinquagesima" in key:
    return "Pre-Lent"

  if date >= church_year.septuagesima and date < church_year.ash_wednesday:
    return "Pre-Lent"

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

  with open(utils.LITURGICAL_YEAR_JSON_PATH, "r", encoding="utf-8") as f:
    liturgical_year_data = json.load(f)

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

      # Check against liturgical_year.json
      matched_items = []
      for item in liturgical_year_data:
        match = False
        if "absolute_date" in item:
          try:
            month_str, day_str = item["absolute_date"].split("-")
            if day.month == int(month_str) and day.day == int(day_str):
              match = True
          except ValueError:
            pass
        elif "relative_date" in item:
          # relative_date is relative to Easter of the current day's year
          target_date = day_cy.easter_date + datetime.timedelta(
              days=item["relative_date"]
          )
          if day == target_date:
            match = True
        elif "rule" in item:
          if item["rule"] == "advent_1":
            target = day_cy.calculate_advent1(day.year)
            if day == target:
              match = True
          elif item["rule"] == "advent_2":
            target = day_cy.calculate_advent1(day.year) + datetime.timedelta(
                days=7
            )
            if day == target:
              match = True
          elif item["rule"] == "advent_3":
            target = day_cy.calculate_advent1(day.year) + datetime.timedelta(
                days=14
            )
            if day == target:
              match = True
          elif item["rule"] == "advent_4":
            target = day_cy.calculate_advent1(day.year) + datetime.timedelta(
                days=21
            )
            if day == target:
              match = True
          elif item["rule"] == "sunday_after_christmas":
            # First Sunday after Dec 25
            christmas = datetime.date(day.year, 12, 25)
            # 6 is Sunday. weekday() returns 0 for Mon, 6 for Sun.
            days_until_sunday = 6 - christmas.weekday()
            if days_until_sunday == 0:
              days_until_sunday = 7
            target = christmas + datetime.timedelta(days=days_until_sunday)
            if day == target:
              match = True
          elif item["rule"].startswith("epiphany_"):
            # epiphany_1 = 1st Sunday after Jan 6
            # epiphany_2 = 2nd Sunday after Jan 6
            try:
              week_num = int(item["rule"].split("_")[1])
              epiphany = datetime.date(day.year, 1, 6)
              days_until_sunday = 6 - epiphany.weekday()
              if days_until_sunday == 0:
                days_until_sunday = 7
              # 1st Sunday
              target = epiphany + datetime.timedelta(days=days_until_sunday)
              # Nth Sunday
              target = target + datetime.timedelta(days=(week_num - 1) * 7)
              if day == target:
                match = True
            except:
              pass

        if match:
          matched_items.append(item)

      json_color = None
      if matched_items:
        # Separate into movable and fixed
        movable = [
            item for item in matched_items if "absolute_date" not in item
        ]
        fixed = [item for item in matched_items if "absolute_date" in item]

        # Display Name: Movable first, then Fixed
        names = [item["Name"] for item in movable] + [
            item["Name"] for item in fixed
        ]
        display_name = " / ".join(names)

        # Color: Movable takes precedence
        if movable:
          if "color" in movable[0]:
            json_color = movable[0]["color"]
        elif fixed:
          if "color" in fixed[0]:
            json_color = fixed[0]["color"]

      # Use display_name for color if available (e.g. "Reformation Day"),
      # otherwise fallback to key (e.g. "Ash Thursday" which has 
      # display_name="")
      color_key = display_name if display_name else key
      if json_color:
        color = json_color
      else:
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
