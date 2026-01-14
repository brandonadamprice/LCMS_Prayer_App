"""Fetches secrets from environment variables or Google Cloud Secret Manager."""

import os
from google.cloud import secretmanager

PROJECT_ID = "978583660884"
_SECRET_VERSION = "latest"


def _get_secret(secret_name, environment_variable, version=_SECRET_VERSION):
  """Fetches a secret from environment variables or Google Cloud Secret Manager."""
  val = None
  if os.getenv(environment_variable) is not None:
    val = os.getenv(environment_variable)
  else:
    try:
      secret_id = (
          f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/{version}"
      )
      client = secretmanager.SecretManagerServiceClient()
      response = client.access_secret_version(name=secret_id)
      val = response.payload.data.decode("UTF-8")
    except Exception as e:
      print(f"Failed to fetch secret: {secret_name} - Error: {e}")
      return None

  if val:
    return val.strip()
  
  print(f"Secret {secret_name} is missing or None.")
  return val


def get_esv_api_key():
  """Fetches the ESV API key."""
  return _get_secret("ESV_API_KEY", "ESV_API_KEY")


def get_google_client_id():
  """Fetches the Google OAuth Client ID."""
  return _get_secret("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_ID")


def get_google_client_secret():
  """Fetches the Google OAuth Client Secret."""
  return _get_secret("GOOGLE_CLIENT_SECRET", "GOOGLE_CLIENT_SECRET")


def get_flask_secret_key():
  """Fetches the Flask SECRET_KEY for session signing."""
  return _get_secret("FLASK_SECRET_KEY", "FLASK_SECRET_KEY")


def get_fernet_key():
  """Fetches the Fernet encryption key."""
  return _get_secret("FERNET_KEY", "FERNET_KEY")


def get_brandon_user_id():
  """Fetches BRANDON_USER_ID."""
  return _get_secret("BRANDON_USER_ID", "BRANDON_USER_ID")


def get_firebase_api_key():
  """Fetches the Firebase API Key."""
  return _get_secret("FIREBASE_API_KEY", "FIREBASE_API_KEY")


def get_firebase_messaging_sender_id():
  """Fetches the Firebase Messaging Sender ID."""
  return _get_secret(
      "FIREBASE_MESSAGING_SENDER_ID", "FIREBASE_MESSAGING_SENDER_ID"
  )


def get_firebase_app_id():
  """Fetches the Firebase App ID."""
  return _get_secret("FIREBASE_APP_ID", "FIREBASE_APP_ID")


def get_firebase_vapid_key():
  """Fetches the Firebase VAPID Key."""
  return _get_secret("FIREBASE_VAPID_KEY", "FIREBASE_VAPID_KEY")


def get_facebook_client_id():
  """Fetches the Facebook App ID."""
  return _get_secret("FACEBOOK_CLIENT_ID", "FACEBOOK_CLIENT_ID")


def get_facebook_client_secret():
  """Fetches the Facebook App Secret."""
  return _get_secret("FACEBOOK_CLIENT_SECRET", "FACEBOOK_CLIENT_SECRET")


def get_ga4_property_id():
  """Fetches the Google Analytics 4 Property ID."""
  return _get_secret("GA4_PROPERTY_ID", "GA4_PROPERTY_ID")


def get_twilio_account_sid():
  """Fetches the Twilio Account SID."""
  return _get_secret("TWILIO_ACCOUNT_SID", "TWILIO_ACCOUNT_SID")


def get_twilio_api_key():
  """Fetches the Twilio API Key (Auth Token)."""
  return _get_secret("TWILIO_API_KEY", "TWILIO_API_KEY")


def get_twilio_phone_number():
  """Fetches the Twilio From Number."""
  return _get_secret("TWILIO_PHONE_NUMBER", "TWILIO_PHONE_NUMBER")


def get_smtp_server():
  """Returns the SMTP server address."""
  return "smtp.gmail.com"


def get_smtp_port():
  """Returns the SMTP port."""
  return 587


def get_smtp_user():
  """Fetches the SMTP username (email address)."""
  return _get_secret("SMTP_USER", "SMTP_USER")


def get_smtp_password():
  """Fetches the SMTP password (app password)."""
  return _get_secret("SMTP_PASSWORD", "SMTP_PASSWORD")
