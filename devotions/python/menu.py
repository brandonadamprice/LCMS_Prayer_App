"""Defines the application menu structure."""


def get_menu_items(is_advent, is_new_year, is_lent):
  """Returns the list of menu items with their properties."""
  return [
      {
          "label": "Daily Prayer",
          "type": "dropdown",
          "submenu": [
              {"label": "Morning", "url": "/morning_devotion", "enabled": True},
              {"label": "Midday", "url": "/midday_devotion", "enabled": True},
              {"label": "Evening", "url": "/evening_devotion", "enabled": True},
              {
                  "label": "Close of Day",
                  "url": "/close_of_day_devotion",
                  "enabled": True,
              },
              {
                  "label": "Night Watch",
                  "url": "/night_watch_devotion",
                  "enabled": True,
              },
              {
                  "label": "Prayer Reminders",
                  "url": "/reminders",
                  "enabled": True,
                  "requires_auth": True,
                  "separator_before": True,
              },
          ],
      },
      {
          "label": "Devotions",
          "type": "dropdown",
          "submenu": [
              {
                  "label": "Advent",
                  "url": "/advent_devotion",
                  "enabled": is_advent,
                  "seasonal": True,
              },
              {
                  "label": "New Year's",
                  "url": "/new_year_devotion",
                  "enabled": is_new_year,
                  "seasonal": True,
              },
              {
                  "label": "Lenten",
                  "url": "/lent_devotion",
                  "enabled": is_lent,
                  "seasonal": True,
              },
              {
                  "label": "Children's",
                  "url": "/childrens_devotion",
                  "enabled": True,
              },
              {"label": "The Litany", "url": "/litany", "enabled": True},
              {
                  "label": "Extended Evening",
                  "url": "/extended_evening_devotion",
                  "enabled": True,
              },
              {
                  "label": "Mid-Week",
                  "url": "/mid_week_devotion",
                  "enabled": True,
              },
          ],
      },
      {
          "label": "Education",
          "type": "dropdown",
          "submenu": [
              {
                  "label": "Small Catechism",
                  "url": "/small_catechism",
                  "enabled": True,
              },
              {
                  "label": "Nicene Creed Study",
                  "url": "/nicene_creed_study",
                  "enabled": True,
              },
              {
                  "label": "Trinity Study",
                  "url": "/trinity_study",
                  "enabled": True,
              },
          ],
      },
      {
          "label": "Bible",
          "type": "dropdown",
          "submenu": [
              {
                  "label": "Daily Lectionary",
                  "url": "/daily_lectionary",
                  "enabled": True,
              },
              {
                  "label": "Psalms",
                  "url": "/psalms_by_category",
                  "enabled": True,
              },
              {
                  "label": "Gospels",
                  "url": "/gospels_by_category",
                  "enabled": True,
              },
              {
                  "label": "Bible in a Year",
                  "url": "/bible_in_a_year",
                  "enabled": True,
              },
              {"label": "Memorization", "url": "/memory", "enabled": True},
          ],
      },
      {
          "label": "Prayer",
          "type": "dropdown",
          "submenu": [
              {
                  "label": "Submit Request",
                  "url": "/prayer_requests",
                  "enabled": True,
              },
              {"label": "Prayer Wall", "url": "/prayer_wall", "enabled": True},
              {"label": "My Prayers", "url": "/my_prayers", "enabled": True},
              {
                  "label": "Short Prayers",
                  "url": "/short_prayers",
                  "enabled": True,
              },
          ],
      },
      {
          "label": "Favorites",
          "type": "dynamic_favorites",
          "requires_auth": True,
          "requires_favorites": True,
          "enabled": True,
      },
      {
          "label": "Calendar",
          "type": "link",
          "url": "/liturgical_calendar",
          "enabled": True,
      },
      {
          "label": "Feedback",
          "type": "link",
          "url": "/feedback",
          "enabled": True,
      },
  ]
