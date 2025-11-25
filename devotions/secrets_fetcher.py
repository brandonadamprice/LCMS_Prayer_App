import os
from google.cloud import secretmanager


def get_esv_api_key():
  """Fetches the ESV API key from the secrets manager."""
  secret_id = "projects/978583660884/secrets/ESV_API_KEY/versions/1"
  secret_manager = secretmanager.SecretManagerServiceClient()
  response = secret_manager.access_secret_version(name=secret_id)
  return response.payload.data.decode("UTF-8")