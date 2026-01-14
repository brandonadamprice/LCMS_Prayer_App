"""Functions for sending notifications via Email, SMS, and Push."""

from email.message import EmailMessage
import logging
import smtplib

import firebase_admin
from firebase_admin import messaging
import secrets_fetcher
from twilio.rest import Client

logger = logging.getLogger(__name__)

# Initialize Firebase Admin if not already initialized
try:
  firebase_admin.get_app()
except ValueError:
  # Explicitly set project ID to ensure correct FCM endpoint usage
  firebase_admin.initialize_app(options={"projectId": "lcms-prayer-app"})


def send_email(
    to_email,
    subject,
    body_html=None,
    body_text=None,
    sender_name="A Simple Way to Pray",
):
  """Sends an email."""
  if not to_email:
    return False

  smtp_server = secrets_fetcher.get_smtp_server()
  smtp_port = secrets_fetcher.get_smtp_port()
  smtp_user = secrets_fetcher.get_smtp_user()
  smtp_password = secrets_fetcher.get_smtp_password()

  if not all([smtp_server, smtp_port, smtp_user, smtp_password]):
    logger.warning("Missing SMTP credentials. Cannot send email.")
    return False

  msg = EmailMessage()
  msg["Subject"] = subject
  msg["From"] = f"{sender_name} <{smtp_user}>"
  msg["To"] = to_email

  if body_text:
    msg.set_content(body_text)
  else:
    msg.set_content("Please enable HTML to view this email.", subtype="plain")

  if body_html:
    msg.add_alternative(body_html, subtype="html")

  try:
    with smtplib.SMTP(smtp_server, smtp_port) as server:
      server.starttls()
      server.login(smtp_user, smtp_password)
      server.send_message(msg)
    logger.info("Email sent to %s", to_email)
    return True
  except Exception as e:
    logger.error("Failed to send email to %s: %s", to_email, e)
    return False


def send_sms(to_phone, message):
  """Sends an SMS."""
  if not to_phone:
    return False

  sid = secrets_fetcher.get_twilio_account_sid()
  token = secrets_fetcher.get_twilio_api_key()
  from_number = secrets_fetcher.get_twilio_phone_number()

  if not (sid and token and from_number):
    logger.warning("Missing Twilio credentials. Cannot send SMS.")
    return False

  try:
    client = Client(sid, token)
    msg = client.messages.create(body=message, from_=from_number, to=to_phone)
    logger.info("SMS sent to %s: %s", to_phone, msg.sid)
    return True
  except Exception as e:
    logger.error(
        "Failed to send SMS to %s. Error: %s. SID used: %s... Token used:"
        " %s... From: %s",
        to_phone,
        e,
        sid[:5] if sid else "None",
        token[:5] if token else "None",
        from_number,
    )
    if hasattr(e, "msg"):
      logger.error("Twilio Error Message: %s", e.msg)
    if hasattr(e, "code"):
      logger.error("Twilio Error Code: %s", e.code)
    return False


def send_push(token, title, body, url=None, data=None):
  """Sends a push notification to a single token."""
  if not token:
    return False

  if data is None:
    data = {}

  data.update({
      "title": title,
      "body": body,
  })
  if url:
    data["url"] = url

  try:
    message = messaging.Message(
        data=data,
        token=token,
    )
    messaging.send(message)
    # Log only first few chars of token for privacy/brevity
    logger.info("Push sent to %s...", token[:10])
    return True
  except Exception as e:
    logger.warning("Failed to send push to %s...: %s", token[:10], e)
    return False
