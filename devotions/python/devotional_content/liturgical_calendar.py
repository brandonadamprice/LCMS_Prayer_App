"""Functions for generating the Liturgical Calendar page."""

import calendar
import datetime
import json
import flask
import liturgy
import pytz
import utils


WHITE_KEYWORDS = [
    "Christmas",
    "Epiphany of Our Lord",
    "All Saints",
    "Trinity",
    "Conversion of St. Paul",
    "Confession of St. Peter",
    "St. John, Apostle",
    "Nativity of St. John the Baptist",
    "Circumcision",
    "Presentation",
    "Annunciation",
    "Visitation",
    "St. Mary",
    "St. Joseph",
    "St. Timothy",
    "St. Titus",
    "Easter",
    "Ascension",
]

RED_KEYWORDS = [
    "Palm Sunday",
    "Pentecost",
    "Reformation",
    "Martyr",
    "Holy Cross",
    "Andrew",
    "Thomas",
    "James",
    "Simon",
    "Jude",
    "Matthew",
    "Luke",
    "Mark",
    "Peter",
    "Paul",
    "Bartholomew",
    "Philip",
    "Barnabas",
    "Matthias",
]

VIOLET_KEYWORDS = ["Ash", "Lent"]
BLACK_KEYWORDS = ["Ash Wednesday", "Good Friday"]
PRE_LENT_KEYWORDS = ["Septuagesima", "Sexagesima", "Quinquagesima"]
SUPPRESS_KEYWORDS = [
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


def get_liturgical_color(key, date, church_year):
  """Determines the liturgical color based on the day key and date."""
  if any(k in key for k in PRE_LENT_KEYWORDS):
    return "Green"

  if any(k in key for k in BLACK_KEYWORDS):
    return "Black"

  if any(k in key for k in WHITE_KEYWORDS):
    return "White"

  if any(k in key for k in RED_KEYWORDS):
    return "Red"

  if any(k in key for k in VIOLET_KEYWORDS):
    return "Violet"

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
  if any(k in key for k in PRE_LENT_KEYWORDS):
    return "Pre-Lent"

  if date >= church_year.septuagesima and date < church_year.ash_wednesday:
    return "Pre-Lent"

  if "Advent" in key:
    return "Advent"
  if "Christmas" in key:
    return "Christmas"
  if "Epiphany" in key:
    return "Epiphany"
  if any(k in key for k in VIOLET_KEYWORDS):
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


def _matches_rule(rule, day, day_cy):
  """Checks if a specific liturgical rule applies to the given day."""
  if rule == "advent_1":
    return day == day_cy.calculate_advent1(day.year)
  elif rule == "advent_2":
    return day == day_cy.calculate_advent1(day.year) + datetime.timedelta(
        days=7
    )
  elif rule == "advent_3":
    return day == day_cy.calculate_advent1(day.year) + datetime.timedelta(
        days=14
    )
  elif rule == "advent_4":
    return day == day_cy.calculate_advent1(day.year) + datetime.timedelta(
        days=21
    )
  elif rule == "sunday_after_christmas":
    christmas = datetime.date(day.year, 12, 25)
    # 6 is Sunday. weekday() returns 0 for Mon, 6 for Sun.
    days_until_sunday = 6 - christmas.weekday()
    if days_until_sunday == 0:
      days_until_sunday = 7
    return day == christmas + datetime.timedelta(days=days_until_sunday)
  elif rule.startswith("epiphany_"):
    try:
      week_num = int(rule.split("_")[1])
      epiphany = datetime.date(day.year, 1, 6)
      days_until_sunday = 6 - epiphany.weekday()
      if days_until_sunday == 0:
        days_until_sunday = 7
      target = epiphany + datetime.timedelta(
          days=days_until_sunday + (week_num - 1) * 7
      )
      return day == target
    except (IndexError, ValueError):
      pass
  elif rule == "reformation_observed":
    reformation_day = datetime.date(day.year, 10, 31)
    if reformation_day.weekday() != 6:  # If not Sunday
      days_to_subtract = reformation_day.weekday() + 1
      target = reformation_day - datetime.timedelta(days=days_to_subtract)
      return day == target
  return False


def _load_liturgical_year_data():
  """Loads liturgical year data from JSON file."""
  with open(utils.LITURGICAL_YEAR_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def generate_calendar_data(year, month):
  """Generates calendar data for the given month and year."""
  cal = calendar.Calendar(firstweekday=6)  # Sunday first
  month_days = cal.monthdatescalendar(year, month)
  liturgical_year_data = _load_liturgical_year_data()

  calendar_rows = []
  today = datetime.date.today()

  for week in month_days:
    week_data = []
    for day in week:
      # Note: day might be from prev/next month
      day_cy = liturgy.ChurchYear(day.year)
      key = day_cy.get_liturgical_key(day)

      # Refine key for display if it is a date string
      display_name = key

      # Suppress ferias and seasonal weekdays
      if key in SUPPRESS_KEYWORDS or (
          "Sunday" not in key
          and (
              key.startswith("Easter")
              or key.startswith("Lent")
              or key.startswith("Advent")
          )
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
          if _matches_rule(item["rule"], day, day_cy):
            match = True

        if match:
          matched_items.append(item)

      json_color = None
      if matched_items:
        # Separate into movable and fixed
        movable = [
            item for item in matched_items if "absolute_date" not in item
        ]
        fixed = [item for item in matched_items if "absolute_date" in item]

        # Priority Handling for Movable Feasts

        # 1. Reformation Day (Observed) trumps other movable feasts on that Sunday (e.g. Trinity #)
        has_reformation_observed = any(
            item["Name"] == "Reformation Day (Observed)" for item in movable
        )
        if has_reformation_observed:
          movable = [
              item
              for item in movable
              if item["Name"] == "Reformation Day (Observed)"
          ]

        # 1b. All Saints' Day (Fixed) overrides movable feasts (like Trinity #) if it falls on Sunday
        has_all_saints = any(
            item["Name"] == "All Saints' Day" for item in fixed
        )
        if has_all_saints:
          # Clear movable feasts (like Trinity 23) if All Saints is present
          movable = []

        # 1c. Advent trumps Trinity
        has_advent = any("Advent" in item["Name"] for item in movable)
        if has_advent:
          movable = [item for item in movable if "Trinity" not in item["Name"]]

        # 2. Remove Epiphany # if a higher priority movable feast exists (Septuagesima, Sexagesima, Quinquagesima, Transfiguration, Lent)
        has_priority_feast = any(
            "Septuagesima" in item["Name"]
            or "Sexagesima" in item["Name"]
            or "Quinquagesima" in item["Name"]
            or "Transfiguration" in item["Name"]
            or "Lent" in item["Name"]
            or "Ash Wednesday" in item["Name"]
            for item in movable
        )

        if has_priority_feast:
          movable = [
              item
              for item in movable
              if "Epiphany" not in item["Name"]
              or "The Baptism of Our Lord" in item["Name"]
              or "Epiphany of Our Lord" in item["Name"]
          ]

        # Display Name: Movable first, then Fixed
        names = [item["Name"] for item in movable] + [
            item["Name"] for item in fixed
        ]
        display_name = " / ".join(names)

        # Color: Movable takes precedence
        if movable:
          # If multiple movable, use the one that survived filtering (e.g. Septuagesima over Epiphany)
          # We just pick the first one's color for now, assuming conflict resolution leaves consistent colors or correct priority is first.
          # Ideally, we should pick color of priority feast if multiple remain.
          # Since we filtered out the lower priority ones, using movable[0] is generally safe.
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
          "full_name": display_name if display_name else key,
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
