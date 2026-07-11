"""Functions for sending notifications via Email, SMS, and Push."""

from email.message import EmailMessage
import logging
import smtplib

import firebase_admin
from firebase_admin import exceptions as firebase_exceptions
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
    logger.error("Failed to send SMS to %s: %s", to_phone, e)
    return False


# Outcomes of a single push send, so callers can decide whether to keep a token.
PUSH_SENT = "sent"
PUSH_INVALID_TOKEN = "invalid_token"  # Token is dead; caller should drop it.
PUSH_ERROR = "error"  # Transient failure; keep the token and retry later.


def send_push_result(token, title, body, url=None, data=None):
  """Sends a push notification to a single token and classifies the outcome.

  Returns one of PUSH_SENT, PUSH_INVALID_TOKEN, or PUSH_ERROR. Callers should
  prune only PUSH_INVALID_TOKEN tokens (which FCM reports as permanently
  unusable); PUSH_ERROR is a transient failure and the token should be kept.
  """
  if not token:
    return PUSH_INVALID_TOKEN

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
        # The notification block is what makes a native app (Capacitor shell)
        # display the message when it is backgrounded or killed — data-only
        # messages are never shown by the OS on Android/iOS. Web push is
        # unaffected: sw.js's custom `push` handler is the only thing that
        # displays there (no firebase-messaging SW library is loaded, so
        # nothing auto-displays twice), and it reads the title/body/url
        # duplicated into `data` above.
        notification=messaging.Notification(title=title, body=body),
        # Reminders are scheduled for a specific time, so ask Android to
        # deliver immediately instead of batching through Doze. The
        # 'reminders' channel is created by app.js in the native shell with
        # high importance (heads-up pop + sound); if a device doesn't have
        # the channel yet, FCM falls back to the app's default channel.
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                channel_id="reminders"
            ),
        ),
        data=data,
        token=token,
    )
    messaging.send(message)
    # Log only first few chars of token for privacy/brevity
    logger.info("Push sent to %s...", token[:10])
    return PUSH_SENT
  except (
      messaging.UnregisteredError,
      messaging.SenderIdMismatchError,
      firebase_exceptions.InvalidArgumentError,
  ) as e:
    # The token is no longer valid (app uninstalled, token rotated, or
    # malformed), so signal the caller to drop it.
    logger.warning("Invalid push token %s...: %s", token[:10], e)
    return PUSH_INVALID_TOKEN
  except Exception as e:
    logger.warning("Failed to send push to %s...: %s", token[:10], e)
    return PUSH_ERROR


def send_push(token, title, body, url=None, data=None):
  """Sends a push notification to a single token. Returns True on success."""
  return send_push_result(token, title, body, url, data) == PUSH_SENT
