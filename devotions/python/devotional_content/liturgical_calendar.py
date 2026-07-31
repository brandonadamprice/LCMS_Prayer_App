"""Functions for generating the Liturgical Calendar and Church Year Wheel pages."""

import calendar
import datetime
import json
import re
from functools import lru_cache

import flask
import liturgy
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


@lru_cache(maxsize=1)
def _load_liturgical_year_data():
  """Loads liturgical year data from JSON file (cached; treat as read-only)."""
  with open(utils.LITURGICAL_YEAR_JSON_PATH, "r", encoding="utf-8") as f:
    return json.load(f)


def _day_info(day):
  """Computes the liturgical info for a single date.

  Shared by the month-grid calendar and the church year wheel so feast
  matching, priority rules, and color selection stay identical between the
  two views.
  """
  day_cy = liturgy.get_church_year(day.year)
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
  liturgical_year_data = _load_liturgical_year_data()
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

  return {
      "day": day.day,
      "date_obj": day,
      "key": display_name,
      "full_name": display_name if display_name else key,
      "color": color.lower(),
      "color_name": color,
      "season": season,
  }


@lru_cache(maxsize=24)
def _generate_calendar_grid(year, month):
  """Builds the month grid (cached; treat as read-only).

  Depends only on (year, month), so the O(days x rules) liturgical matching is
  computed once per month and reused across requests. The per-request is_today
  flag is applied later by generate_calendar_data, not here.
  """
  cal = calendar.Calendar(firstweekday=6)  # Sunday first
  month_days = cal.monthdatescalendar(year, month)

  calendar_rows = []
  for week in month_days:
    week_data = []
    for day in week:
      # Note: day might be from prev/next month
      week_data.append({**_day_info(day), "is_current_month": day.month == month})
    calendar_rows.append(week_data)

  return calendar_rows


def generate_calendar_data(year, month):
  """Returns the month grid for (year, month) with today's cell flagged.

  The heavy liturgical computation is cached by _generate_calendar_grid; this
  overlays the per-request is_today flag onto fresh copies so the cached grid
  is never mutated.
  """
  today = datetime.date.today()
  return [
      [{**day, "is_today": day["date_obj"] == today} for day in week]
      for week in _generate_calendar_grid(year, month)
  ]


def generate_liturgical_calendar_page():
  """Generates HTML for the Liturgical Calendar page."""
  eastern_timezone = utils.EASTERN_TZ
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

  return flask.render_template("liturgical_calendar.html", **template_data)


# Numbered Sundays ("Trinity 12", "Epiphany 3", ...) get small ticks on the
# wheel rather than feast markers and are left out of the festival list.
_NUMBERED_SUNDAY_RE = re.compile(r"^(Advent|Epiphany|Lent|Easter|Trinity) \d+$")


@lru_cache(maxsize=8)
def _build_wheel_data(start_year):
  """Builds per-day data for one church year (cached; treat as read-only).

  The church year runs from Advent 1 of start_year to the eve of Advent 1 of
  start_year + 1 (364 or 371 days; day 0 is always a Sunday). Each day gets
  the same feast/color resolution as the month calendar plus the broad season
  from liturgy.get_church_season, so the wheel's rings agree with the grid.
  """
  advent1 = liturgy.get_church_year(start_year).calculate_advent1(start_year)
  end = liturgy.get_church_year(start_year + 1).calculate_advent1(
      start_year + 1
  )

  days = []
  majors = []
  day = advent1
  index = 0
  while day < end:
    info = _day_info(day)
    # Outside the movable season an unnamed day's key is the fixed-date
    # string ("17 Jun"); treat that as "no name" (the month grid does the
    # same suppression in its template).
    date_key = day.strftime("%d %b")
    name = info["key"] if info["key"] != date_key else ""
    detail = info["full_name"] if info["full_name"] != date_key else ""
    days.append({
        "d": day.isoformat(),
        "n": name,
        "k": detail if not name else "",
        "c": info["color_name"],
        "s": liturgy.get_church_season(day),
    })
    if name and not _NUMBERED_SUNDAY_RE.match(name):
      majors.append({
          "i": index,
          "n": name,
          "c": info["color_name"],
          "date": f"{calendar.month_abbr[day.month]} {day.day}, {day.year}",
      })
    day += datetime.timedelta(days=1)
    index += 1

  return {"start_year": start_year, "days": days, "majors": majors}


def generate_church_year_wheel_page():
  """Generates HTML for the interactive Church Year Wheel page."""
  today = datetime.datetime.now(utils.EASTERN_TZ).date()

  # The church year containing today: it starts this calendar year if we are
  # already past Advent 1, otherwise it started last year.
  today_advent1 = liturgy.get_church_year(today.year).calculate_advent1(
      today.year
  )
  current_start_year = today.year if today >= today_advent1 else today.year - 1

  try:
    start_year = int(flask.request.args.get("start_year", current_start_year))
  except ValueError:
    start_year = current_start_year
  # Gregorian calendar range; also keeps the lru_cache from being churned by
  # nonsense values.
  start_year = max(1583, min(start_year, 9000))

  wheel = _build_wheel_data(start_year)

  advent1 = datetime.date.fromisoformat(wheel["days"][0]["d"])
  today_index = (today - advent1).days
  if not 0 <= today_index < len(wheel["days"]):
    today_index = -1

  return flask.render_template(
      "church_year_wheel.html",
      wheel=wheel,
      majors=wheel["majors"],
      today_index=today_index,
      start_year=start_year,
      prev_start_year=start_year - 1,
      next_start_year=start_year + 1,
      is_current_year=start_year == current_start_year,
  )
