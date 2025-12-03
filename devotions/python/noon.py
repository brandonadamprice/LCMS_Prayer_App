"""Functions for generating the noon devotion."""

import datetime
import random
import flask
import pytz
import utils

NOON_READINGS = [
    "1 Corinthians 7:17,23-24",
    "Luke 23:44-46",
    "Matthew 5:13-16",
    "Matthew 13:1-9;18-23",
    "Mark 13:24-27",
    "John 15:1-9",
    "Romans 7:18-25",
    "Romans 12:1-2",
    "1 Peter 1:3-9",
    "Revelation 7:13-17",
]

CONCLUDING_PRAYERS = [
    (
        "Blessed Lord Jesus Christ, at this hour You hung upon the cross,"
        " stretching out Your loving arms to embrace the world in Your death."
        " Grant that all people of the earth may look to You and see their"
        " salvation; for Your mercy's sake we pray. Amen."
    ),
    (
        "Heavenly Father, send Your Holy Spirit into our hearts to direct and"
        " rule us according to Your will to comfort us in all our afflictions,"
        " to defend us from all error, and to lead us into all truth; through"
        " Jesus Christ, our Lord. Amen."
    ),
]


def generate_noon_devotion():
  """Generates HTML for the noon devotion for the current date."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  template_data = utils.get_devotion_data(now)

  del template_data["catechism_title"]
  del template_data["catechism_text"]
  del template_data["catechism_meaning_html"]
  del template_data["catechism_prayer"]
  del template_data["prayer_topic"]
  del template_data["weekly_prayer_html"]

  reading_ref = random.choice(NOON_READINGS)
  psalm_num = random.randint(1, 150)
  psalm_ref = f"Psalm {psalm_num}"

  reading_text, psalm_text = utils.fetch_passages([reading_ref, psalm_ref])
  template_data["reading_ref"] = reading_ref
  template_data["reading_text"] = reading_text
  template_data["psalm_ref"] = psalm_ref
  template_data["psalm_text"] = psalm_text
  template_data["concluding_prayer"] = random.choice(CONCLUDING_PRAYERS)

  print("Generated Noon HTML")
  return flask.render_template("noon_devotion.html", **template_data)
