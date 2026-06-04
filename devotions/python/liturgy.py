"""Calculates and provides key dates for the Western Christian liturgical year.

This class is used to determine dates such as Easter, Ash Wednesday,
Pentecost, and Holy Trinity Sunday for a given year, which are essential
for looking up lectionary readings.
"""

import datetime
import functools

# Liturgical weeks begin on Sunday, so index 0 is Sunday. (This differs from
# datetime.weekday(), where Monday is 0.)
_WEEKDAY_NAMES = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)


class ChurchYear:
  """Calculates and provides key dates for the Western Christian liturgical year."""

  def __init__(self, year: int):
    self.year = year
    self.easter_date = self.calculate_easter(year)
    self.ash_wednesday = self.easter_date - datetime.timedelta(days=46)
    self.pentecost = self.easter_date + datetime.timedelta(days=49)
    self.holy_trinity = self.pentecost + datetime.timedelta(days=7)
    self.septuagesima = self.easter_date - datetime.timedelta(days=63)
    self.sexagesima = self.easter_date - datetime.timedelta(days=56)
    self.quinquagesima = self.easter_date - datetime.timedelta(days=49)

  def calculate_advent1(self, year: int) -> datetime.date:
    """Advent 1 is the Sunday between Nov 27 and Dec 3."""
    return datetime.date(year, 12, 3) - datetime.timedelta(
        days=(datetime.date(year, 12, 3).weekday() + 1) % 7
    )

  def get_week_of_church_year(self, current_date: datetime.date) -> int:
    """Returns week number 1-53 within church year starting Advent 1."""
    adv1_this_year = self.calculate_advent1(current_date.year)
    if current_date >= adv1_this_year:
      start_of_cy = adv1_this_year
    else:
      start_of_cy = self.calculate_advent1(current_date.year - 1)

    week = ((current_date - start_of_cy).days // 7) + 1
    return week

  def calculate_easter(self, year: int) -> datetime.date:
    """Calculates the date of Western Easter for a given year."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(year, month, day)

  def get_liturgical_key(self, current_date: datetime.date) -> str:
    """Determines the correct CSV key for the current date.

    Prioritizes the Movable Season (Ash Wed -> Trinity Sunday). If not in that
    season, returns the Fixed Date (e.g., "01 Jan").
    """
    # Convert to date object if it's datetime
    if isinstance(current_date, datetime.datetime):
      d = current_date.date()
    else:
      d = current_date

    # Check if we are in the Movable Season
    if self.ash_wednesday <= d <= self.holy_trinity:

      # CASE 1: Ash Wednesday to Holy Saturday
      if d < self.easter_date:
        days_since_ash = (d - self.ash_wednesday).days
        if days_since_ash == 0:
          return "Ash Wednesday"
        if days_since_ash == 1:
          return "Ash Thursday"
        if days_since_ash == 2:
          return "Ash Friday"
        if days_since_ash == 3:
          return "Ash Saturday"

        # Lent Weeks
        days_into_lent = days_since_ash - 4
        week_num = (days_into_lent // 7) + 1
        weekday = _WEEKDAY_NAMES[days_into_lent % 7]

        # Special names for Holy Week (Lent 6)
        if week_num == 6:
          if weekday == "Sunday":
            return "Palm Sunday"
          if weekday == "Monday":
            return "Holy Week Monday"
          if weekday == "Tuesday":
            return "Holy Week Tuesday"
          if weekday == "Wednesday":
            return "Holy Week Wednesday"
          if weekday == "Thursday":
            return "Maundy Thursday"
          if weekday == "Friday":
            return "Good Friday"
          if weekday == "Saturday":
            return "Holy Saturday"

        return f"Lent {week_num} {weekday}"

      # CASE 2: Easter Season
      days_since_easter = (d - self.easter_date).days
      week_num = (days_since_easter // 7) + 1
      weekday = _WEEKDAY_NAMES[days_since_easter % 7]

      if days_since_easter == 0:
        return "Easter Sunday"
      if days_since_easter == 39:
        return "Ascension Day"  # 40th day is Ascension (Thurs)
      if days_since_easter == 49:
        return "Pentecost Sunday"
      if days_since_easter >= 50 and days_since_easter < 56:
        # Pentecost Week (Often called Pentecost Monday etc)
        return f"Pentecost {weekday}"
      if days_since_easter == 56:
        return "Holy Trinity"

      # Standard Easter Weeks
      prefix = "Easter" if week_num == 1 else f"Easter {week_num}"
      return f"{prefix} {weekday}"

    # CASE 3: Fixed Date (Ordinary Time / Epiphany / Advent)
    return current_date.strftime("%d %b")

  def get_mid_week_lectionary_key(self, current_date) -> str:
    """Returns the mid-week lectionary key for the given date.

    The key identifies the Sunday or major festival whose readings should be
    used for the week containing the date (e.g. "advent_1", "christmas_day",
    "lent_3", "trinity_5", "last_sunday").

    The mid-week reading for any day comes from the most recent "marker" on
    or before that day: the most recent Sunday, or — if a higher festival
    has occurred since then — Christmas Day, Epiphany, or Ash Wednesday.
    Sundays are then identified by their position relative to Easter and
    Advent 1, which correctly accounts for years with variable numbers of
    Epiphany and Trinity Sundays.
    """
    if isinstance(current_date, datetime.datetime):
      current_date = current_date.date()

    # Determine which church year this date belongs to.
    advent1_this = self.calculate_advent1(current_date.year)
    if current_date >= advent1_this:
      cy_advent = advent1_this
      easter = self.calculate_easter(current_date.year + 1)
    else:
      cy_advent = self.calculate_advent1(current_date.year - 1)
      easter = self.calculate_easter(current_date.year)

    next_advent = self.calculate_advent1(cy_advent.year + 1)

    # Anchor dates for the church year.
    christmas_day = datetime.date(cy_advent.year, 12, 25)
    epiphany = datetime.date(cy_advent.year + 1, 1, 6)
    septuagesima = easter - datetime.timedelta(days=63)
    ash_wed = easter - datetime.timedelta(days=46)
    transfiguration_sun = septuagesima - datetime.timedelta(days=7)
    palm_sun = easter - datetime.timedelta(days=7)
    pentecost = easter + datetime.timedelta(days=49)
    trinity = easter + datetime.timedelta(days=56)
    last_sunday_of_year = next_advent - datetime.timedelta(days=7)

    # Find the most recent significant marker on or before current_date:
    # the most recent Sunday, optionally overridden by Christmas Day,
    # Epiphany, or Ash Wednesday if one fell since that Sunday.
    days_since_sunday = (current_date.weekday() + 1) % 7
    last_sunday = current_date - datetime.timedelta(days=days_since_sunday)

    anchor = last_sunday
    for festival in (christmas_day, epiphany, ash_wed):
      if last_sunday < festival <= current_date:
        anchor = max(anchor, festival)

    # Festivals and movable Sundays with fixed-offset positions.
    if anchor == christmas_day:
      return "christmas_day"
    if anchor == epiphany:
      return "epiphany"
    if anchor == ash_wed:
      return "ash_wednesday"
    if anchor == transfiguration_sun:
      return "transfiguration"
    if anchor == palm_sun:
      return "palmarum"
    if anchor == easter:
      return "easter_day"
    if anchor == pentecost:
      return "pentecost"
    if anchor == trinity:
      return "trinity"
    if anchor == last_sunday_of_year:
      return "last_sunday"

    # Pre-Lent Sundays.
    if anchor == septuagesima:
      return "septuagesima"
    if anchor == septuagesima + datetime.timedelta(days=7):
      return "sexagesima"
    if anchor == septuagesima + datetime.timedelta(days=14):
      return "quinquagesima"

    # Lent Sundays. Lent 1 is the first Sunday after Ash Wednesday.
    lent_1_sunday = ash_wed + datetime.timedelta(days=4)
    for i in range(1, 6):
      if anchor == lent_1_sunday + datetime.timedelta(days=(i - 1) * 7):
        return f"lent_{i}"

    # Easter Sundays (Easter 2 through Easter 6, then Exaudi).
    for i in range(2, 7):
      if anchor == easter + datetime.timedelta(days=(i - 1) * 7):
        return f"easter_{i}"
    if anchor == easter + datetime.timedelta(days=42):
      return "exaudi"

    # Advent Sundays.
    if cy_advent <= anchor < christmas_day:
      week = min((anchor - cy_advent).days // 7 + 1, 4)
      return f"advent_{week}"

    # Sundays between Christmas Day and Epiphany.
    if christmas_day < anchor < epiphany:
      return _christmas_season_sunday_key(anchor, christmas_day)

    # Sundays between Epiphany and Transfiguration.
    if epiphany < anchor < transfiguration_sun:
      return _epiphany_season_sunday_key(anchor, epiphany)

    # Sundays after Trinity, before Last Sunday.
    if trinity < anchor < last_sunday_of_year:
      week = (anchor - trinity).days // 7
      return f"trinity_{week}"

    return None


def _first_sunday_strictly_after(date: datetime.date) -> datetime.date:
  """Returns the first Sunday strictly after the given date."""
  days_ahead = (6 - date.weekday()) % 7
  if days_ahead == 0:
    days_ahead = 7
  return date + datetime.timedelta(days=days_ahead)


def _christmas_season_sunday_key(sunday: datetime.date,
                                 christmas_day: datetime.date) -> str:
  """Returns the key for a Sunday strictly between Christmas Day and Epiphany."""
  first_sun = _first_sunday_strictly_after(christmas_day)
  if sunday < first_sun + datetime.timedelta(days=7):
    return "sunday_after_christmas"
  return "second_sunday_after_christmas"


def _epiphany_season_sunday_key(sunday: datetime.date,
                                epiphany: datetime.date) -> str:
  """Returns the key for a Sunday strictly between Epiphany and Transfiguration."""
  first_sun = _first_sunday_strictly_after(epiphany)
  weeks = (sunday - first_sun).days // 7 + 1
  return f"epiphany_{weeks}"


@functools.lru_cache(maxsize=128)
def get_church_year(year: int) -> ChurchYear:
  """Returns a cached ChurchYear for the given year.

  ChurchYear instances are immutable after construction and their methods are
  pure, so a single instance per year can be shared safely across requests.
  """
  return ChurchYear(year)
