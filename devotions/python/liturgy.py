"""Calculates and provides key dates for the Western Christian liturgical year.

This class is used to determine dates such as Easter, Ash Wednesday,
Pentecost, and Holy Trinity Sunday for a given year, which are essential
for looking up lectionary readings.
"""

import datetime


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
        day_names = [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]
        weekday = day_names[days_into_lent % 7]

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
      day_names = [
          "Sunday",
          "Monday",
          "Tuesday",
          "Wednesday",
          "Thursday",
          "Friday",
          "Saturday",
      ]
      weekday = day_names[days_since_easter % 7]

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
