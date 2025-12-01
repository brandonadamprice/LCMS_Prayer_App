"""Functions for generating the Advent devotion."""

import datetime
import os
import string
import pytz
import utils

ADVENT_HTML_TEMPLATE_PATH = os.path.join(
    utils.SCRIPT_DIR, "..", "html", "advent_devotion.html"
)

CLOSING_PRAYER_HTML = """<p>O Lord, our heavenly Father, almighty and everlasting God, who hast safely brought us to the beginning of this day, defend us in the same with Thy mighty power and grant that this day we fall into no sin, neither run into any kind of danger, but that all our doings, being ordered by Thy governance, may be righteous in Thy sight; through Jesus Christ, Thy Son, our Lord, who liveth and reigneth with Thee and the Holy Ghost, ever one God, world without end. <strong>Amen</strong>.</p>"""

ADVENT_DAILY_DEVOTIONS = {
    1: {
        "title": "The King's Assurance",
        "readings": ["Isaiah 7:10-8:8", "1 Peter 3:1–22"],
        "meditation": (
            """The Christian is called to <strong>live out their baptism by daily contrition and repentance</strong>. We pray that God would keep us this day from sin and all evil, that all our doings and life may please Him. In your home, strive to be a “real Church” where you properly govern and teach your child to the honor of God. <strong>Collect for Grace:</strong> O Lord, our heavenly Father... grant that this day we fall into no sin, neither run into any kind of danger, but that all our doings... may be righteous in Thy sight."""
        ),
    },
    2: {
        "title": "Watchfulness and Sobriety",
        "readings": ["Isaiah 8:9-9:7", "1 Peter 4:1–19"],
        "meditation": (
            """The Advent Season calls us to preparation. We look for Christ's return in glory. We ask God for grace to put away fleshly lusts so that we may be ready for Thy visitation. <strong>The Christian life is a continual spiritual warfare</strong>."""
        ),
    },
    3: {
        "title": "The Sanctuary of the Word",
        "readings": ["Isaiah 9:8-10:4", "2 Peter 1:1–21"],
        "meditation": (
            """The Word of God creates faith and is the means of grace. We must be <strong>constantly engaged upon God's Word</strong>, carrying it in our hearts and upon our lips. The life of faith centers on meditation on the Word of God."""
        ),
    },
    4: {
        "title": "The Righteous Branch",
        "readings": ["Isaiah 11:1-12:6", "2 Peter 2:1–22"],
        "meditation": (
            """The Advent Responsory speaks of the <strong>righteous Branch</strong> the Lord will raise unto David, who shall reign and execute judgment and justice. This points to the fulfillment of prophecy in Christ. The Advent Proper Preface specifically mentions Christ’s way prepared by John the Baptist."""
        ),
    },
    5: {
        "title": "Hope and Deliverance",
        "readings": ["Isaiah 13:1-14:2", "2 Peter 3:1–18"],
        "meditation": (
            """The Advent Season gladdens us with the <strong>yearly anticipation of our redemption</strong>. Our life is sustained by daily return to baptism in repentance and faith. We receive deliverance in Christ's precious gifts."""
        ),
    },
    6: {
        "title": "Preparing the Way",
        "readings": ["Isaiah 14:3-27", "1 John 1:1–2:11"],
        "meditation": (
            """We wait for the Lord, <strong>whose way John the Baptist prepared, proclaiming Him the Messiah</strong>. The ultimate source of our prayer is the gift of the Holy Spirit, received in Baptism. The Christian life is a life lived in baptism."""
        ),
    },
    7: {
        "title": "The Coming of Salvation",
        "readings": ["Isaiah 14:28-16:14", "1 John 2:12–28"],
        "meditation": (
            """<strong>Introit:</strong> <strong>Daughter of Zion: behold, thy Salvation cometh.</strong> The Lord shall cause His glorious voice to be heard: and ye shall have gladness of heart. <strong>Collect:</strong> <strong>Stir up our hearts, O Lord, to make ready the way of Thine only-begotten Son, so that by His coming we may be enabled to serve Thee with pure minds</strong>. <strong>Meditation:</strong> The Lord’s advent should move us to solemnly meditate on His blessed advent into the flesh, finding in it genuine comfort for our troubled souls."""
        ),
    },
    8: {
        "title": "Living the Baptized Life",
        "readings": ["Isaiah 17:1-18:7", "1 John 2:29–3:10"],
        "meditation": (
            """The Christian is called to <strong>live in the promises of Holy Baptism</strong>. Baptism is not merely a past act but a <strong>present-tense reality</strong> of the Christian's existence in repentance and faith. We receive forgiveness, peace, and being God’s child in the means of grace, which we must immediately give out again through the service of our fellow man in our <strong>daily calling</strong>."""
        ),
    },
    9: {
        "title": "Following Christ",
        "readings": ["Isaiah 19:1-20:6", "1 John 3:11–24"],
        "meditation": (
            """We pray for grace to <strong>follow Him in heart and life</strong>. The Christian life is a <strong>great service</strong> on the part of every Christian priest (believer). Every Christian is a priest before God. Pray for one’s calling and daily work."""
        ),
    },
    10: {
        "title": "Instruction in the Home",
        "readings": ["Isaiah 21:1-22:14", "1 John 4:1–6"],
        "meditation": (
            """The Catechism is intended for use in the <strong>family and for teaching to the children</strong>. When a child begins to understand the faith, they should be encouraged to bring home verses of Scripture from the sermon and repeat them at mealtime. <strong>Parents are responsible to God for instructing their household</strong>."""
        ),
    },
    11: {
        "title": "The Unchanging Lord",
        "readings": ["Isaiah 22:15-25", "1 John 4:7–21"],
        "meditation": (
            """Christ is the center of time. We acknowledge the epitome of God’s will, the sending of His Son into the flesh for salvation. We pray for fruitful and salutary use of the blessed Sacrament of Christ’s body and blood, trusting that His body and blood are <strong>really present... and are there distributed and received</strong>."""
        ),
    },
    12: {
        "title": "Trusting the Truth",
        "readings": ["Isaiah 23:1-24:23", "1 John 5:1–21"],
        "meditation": (
            """We ask that our faith may be increased, so we may joyfully and firmly confess that Thy Word is the truth. The Christian life is lived by the daily return to baptism in repentance and faith. Our life is lived <strong>coram Deo-ly by faith</strong>."""
        ),
    },
    13: {
        "title": "Rejoicing in Hope",
        "readings": ["Isaiah 25:1-26:10", "2 John 1–13"],
        "meditation": (
            """We look toward the King who shall reign and prosper. We are called to keep the feast of the appearing of the true Light divine. The anticipation of salvation brings <strong>gladness of heart</strong>."""
        ),
    },
    14: {
        "title": "The Lord Is at Hand",
        "readings": ["Isaiah 26:11-27:13", "3 John 1–15"],
        "meditation": (
            """<strong>Introit:</strong> <strong>Rejoice in the Lord alway: and again I say, Rejoice.</strong> Let your moderation be known unto all men: <strong>the Lord is at hand</strong>. <strong>Collect:</strong> <strong>Mercifully hear, O Lord, the prayers of Thy people, that, as they rejoice in the advent of Thine only-begotten Son according to the flesh, so when He cometh a second time in His majesty, they may receive the reward of eternal life</strong>. <strong>Meditation:</strong> Advent stresses that Christ's coming should move us to solemn meditation. We pray for those afflicted by sickness or despair, that God may take them into His care."""
        ),
    },
    15: {
        "title": "Daily Repentance",
        "readings": ["Isaiah 28:1-22", "Jude 1–25"],
        "meditation": (
            """The Christian life is nothing other than <strong>a daily baptism</strong>. Baptism “does not remove original sin... rather, it is the continued and permanent promise of God to the believer”. The Commandments remind us of our sin. We should diligently examine ourselves, considering: Have I hurt someone by my words or deeds?."""
        ),
    },
    16: {
        "title": "The Glorious King",
        "readings": ["Isaiah 28:23-29:14", "Revelation 1:1–20"],
        "meditation": (
            """The Second Advent is to be <strong>in power and great glory</strong>. We look toward the King who shall reign and prosper and execute judgment. The entire incarnation is a revelation or apocalypse of God’s eschatological agent, Jesus."""
        ),
    },
    17: {
        "title": "Ingrafting the Word",
        "readings": ["Isaiah 29:15-30:17", "Revelation 2:1–17"],
        "meditation": (
            """The Word we hear in the service should be <strong>so engrafted in my heart that I may bring forth the fruit of the Spirit</strong>. The liturgical service contains large quotations from the Bible, making them invaluable for their educational value."""
        ),
    },
    18: {
        "title": "The Lord's Mercy",
        "readings": ["Isaiah 30:18-33", "Revelation 2:18–3:6"],
        "meditation": (
            """We trust in God’s tender mercies, for they have been ever of old. We look to the blessed hope, the appearing of the glory of our great God and Savior Jesus Christ. We should follow Christ’s example of compassion."""
        ),
    },
    19: {
        "title": "Holiness of Living",
        "readings": ["Isaiah 32:1-33:6", "Revelation 3:7–22"],
        "meditation": (
            """We are stirred up to holiness of living, ever mindful of the day of judgment. Holiness is documented in Christian behavior. We are to present our bodies a living sacrifice, holy, acceptable to God, which is our reasonable service."""
        ),
    },
    20: {
        "title": "Gladness of Heart",
        "readings": ["Isaiah 33:17-35:10", "Revelation 4:1–5:14"],
        "meditation": (
            """The Collect prays that we who joyfully receive Christ as Redeemer may <strong>behold Him without fear when He cometh as our Judge</strong>. The anticipation of salvation brings gladness of heart."""
        ),
    },
    21: {
        "title": "The Way of the Lord",
        "readings": ["Isaiah 36:1-37:20", "Revelation 6:1–7:17"],
        "meditation": (
            """<strong>Introit:</strong> <strong>Drop down, ye heavens, from above: and let the skies pour down righteousness.</strong> Let the earth open: and bring forth salvation. <strong>Collect:</strong> <strong>Stir up Thy power, O Lord, and come, that by Thy protection we may be rescued from the threatening perils of our sins, and saved by Thy mighty deliverance</strong>. <strong>Proper Preface:</strong> Through Jesus Christ, our Lord, <strong>whose way John the Baptist prepared, proclaiming Him the Messiah</strong>."""
        ),
    },
    22: {
        "title": "The Word Made Flesh",
        "readings": ["Isaiah 37:21-38", "Revelation 8:1–13"],
        "meditation": (
            """The first half of the Church Year is <strong>geared to move toward Good Friday and Easter, which flows from the Time of Christmas</strong>. We rejoice that God gave His eternal Word to be made incarnate of the pure Virgin. Christ was born in the lowliness of Bethlehem to be the sacrifice for sin."""
        ),
    },
    23: {
        "title": "Revelation of Glory",
        "readings": ["Isaiah 43:1-24", "Revelation 9:13–10:11"],
        "meditation": (
            """Christmas celebrates the mystery of the Word made flesh. In Him, being found in fashion as a man, <strong>Thou didst manifest the fullness of Thy glory</strong>. The inward reality is widely different from the outward appearance: <strong>An Infant wails; angels are heard in praise</strong>."""
        ),
    },
    24: {
        "title": "Redemption is Near",
        "readings": ["Isaiah 44:21-45:13", "Revelation 12:1–17"],
        "meditation": (
            """<strong>Invitatory (Christmastide):</strong> <strong>Unto us the Christ is born: Oh, come, let us worship Him</strong>. <strong>Responsory:</strong> <strong>The Word was made flesh and dwelt among us. And we beheld His glory, the glory as of the Only-begotten of the Father, full of grace and truth</strong>. <strong>Meditation:</strong> The Lord hath sent redemption unto His people."""
        ),
    },
    25: {
        "title": "Christ is Born!",
        "readings": ["Isaiah 49:1-18", "Matthew 1:1–17"],
        "meditation": (
            """<strong>Invitatory:</strong> <strong>Unto us the Christ is born: Oh, come, let us worship Him</strong>. <strong>Collect:</strong> <strong>Most merciful God, who hast given Thine eternal Word to be made incarnate of the pure Virgin, grant unto Thy people grace to put away fleshly lusts that so they may be ready for Thy visitation</strong>. <strong>Proper Preface (Christmas):</strong> For in the mystery of the Word made flesh Thou hast given us a new revelation of Thy glory. <strong>Meditation:</strong> Today the Maker of the world was born of a Virgin’s womb, and He, who made all natures, became Son of her, whom He created."""
        ),
    },
}


def generate_advent_devotion():
  """Generates HTML for the Advent devotion."""
  eastern_timezone = pytz.timezone("America/New_York")
  now = datetime.datetime.now(eastern_timezone)
  day_of_month = now.day

  devotion_data = ADVENT_DAILY_DEVOTIONS.get(day_of_month)
  if not devotion_data:
    devotion_data = ADVENT_DAILY_DEVOTIONS[1]  # Default to 1st if out of range

  readings = devotion_data["readings"]
  reading_texts = utils.fetch_passages(readings)

  readings_html = ""
  for i, ref in enumerate(readings):
    readings_html += (
        f'<p class="subheader"><strong>{ref}</strong></p><p>{reading_texts[i]}</p>'
    )
    if i < len(readings) - 1:
      readings_html += "<hr>"

  meditation_html = f'<p>{devotion_data["meditation"]}</p>'

  template_data = {
      "date_str": now.strftime("%A, %B %d, %Y"),
      "devotion_title": devotion_data["title"],
      "apostles_creed_html": utils.APOSTLES_CREED_HTML,
      "lords_prayer_html": utils.LORDS_PRAYER_HTML,
      "reading_refs": " & ".join(readings),
      "readings_html": readings_html,
      "meditation_html": meditation_html,
      "closing_prayer_html": CLOSING_PRAYER_HTML,
  }

  with open(ADVENT_HTML_TEMPLATE_PATH, "r", encoding="utf-8") as f:
    template = string.Template(f.read())

  html = template.substitute(template_data)
  print("Generated Advent HTML")
  return html
