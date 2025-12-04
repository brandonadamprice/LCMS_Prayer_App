"""Functions for interacting with Firestore prayer requests."""

import datetime
import random
from google.cloud import firestore
from google.cloud.firestore_v1 import base_query
from google.cloud.firestore_v1 import query as firestore_query_module
import utils

NAME_MAX_LENGTH = 100
REQUEST_MAX_LENGTH = 1000
PROJECT_ID = "lcms-prayer-app"
DATABASE_ID = "prayer-app-datastore"
COLLECTION_NAME = "prayer-requests"


def get_db_client():
  """Initializes and returns a Firestore client."""
  # In a GCP environment (Cloud Run, GAE), the client automatically
  # authenticates using the service account or application default credentials.
  # For local development, ensure you have authenticated via gcloud:
  # `gcloud auth application-default login`
  return firestore.Client(project=PROJECT_ID, database=DATABASE_ID)


def add_prayer_request(name: str, request: str, days_ttl: int = 30):
  """Adds a prayer request to the Firestore database if content is appropriate.

  Returns:
      tuple[bool, str | None]: (True, None) if successful, or (False,
      error_message) on failure.
  """
  try:
    days_ttl = int(days_ttl)
    if not 1 <= days_ttl <= 90:
      return (
          False,
          f"Invalid duration: {days_ttl}. Must be between 1 and 90 days.",
      )
  except (ValueError, TypeError):
    return False, f"Invalid duration: {days_ttl}. Must be an integer."
  if not name or not name.strip() or not request or not request.strip():
    return False, "Prayer request name or request cannot be empty."
  if len(name) > NAME_MAX_LENGTH or len(request) > REQUEST_MAX_LENGTH:
    return (
        False,
        (
            "Prayer request content exceeds length limits (100 characters for"
            " name, 1000 for request)."
        ),
    )
  if utils.contains_phone_number(name) or utils.contains_phone_number(request):
    return (
        False,
        "Prayer requests cannot contain phone numbers or similar patterns.",
    )
  if utils.is_inappropriate(name) or utils.is_inappropriate(request):
    return False, "Inappropriate content detected in prayer request."
  db = get_db_client()
  collection_ref = db.collection(COLLECTION_NAME)
  created_at = datetime.datetime.now(datetime.timezone.utc)
  expires_at = created_at + datetime.timedelta(days=days_ttl)
  collection_ref.add({
      "name": name,
      "request": request,
      "created_at": created_at,
      "expires_at": expires_at,
      "pray_count": 0,
  })
  return True, None


def get_active_prayer_requests():
  """Returns a list of active prayer requests from Firestore."""
  db = get_db_client()
  now = datetime.datetime.now(datetime.timezone.utc)
  collection_ref = db.collection(COLLECTION_NAME)
  # Note: Firestore may require a composite index for this query.
  query = collection_ref.where(
      filter=base_query.FieldFilter("expires_at", ">", now)
  ).order_by("created_at", direction=firestore_query_module.Query.DESCENDING)
  docs = query.stream()
  requests = []
  for doc in docs:
    data = doc.to_dict()
    data["id"] = doc.id
    requests.append(data)
  return requests


def get_prayer_wall_requests(limit: int = 10) -> list[dict]:
  """Returns a random sample of active prayer requests."""
  active_requests = get_active_prayer_requests()
  if not active_requests:
    return []
  if len(active_requests) <= limit:
    random.shuffle(active_requests)
    return active_requests
  else:
    return random.sample(active_requests, limit)


def update_pray_count(request_id: str, operation: str) -> bool:
  """Increments or decrements the pray count for a given request."""
  db = get_db_client()
  doc_ref = db.collection(COLLECTION_NAME).document(request_id)
  try:
    if operation == "increment":
      doc_ref.update({"pray_count": firestore.Increment(1)})
    elif operation == "decrement":
      doc_ref.update({"pray_count": firestore.Increment(-1)})
    else:
      return False
    return True
  except Exception as e:
    print(f"Error updating pray count for {request_id}: {e}")
    return False


def remove_expired_requests():
  """Removes expired prayer requests from the Firestore database."""
  db = get_db_client()
  now = datetime.datetime.now(datetime.timezone.utc)
  collection_ref = db.collection(COLLECTION_NAME)
  # Queries for expired docs
  query = collection_ref.where(
      filter=base_query.FieldFilter("expires_at", "<=", now)
  )
  docs_to_delete = list(query.stream())

  if not docs_to_delete:
    return

  batch = db.batch()
  deleted_count = 0
  for doc in docs_to_delete:
    batch.delete(doc.reference)
    deleted_count += 1
    # Firestore batches are limited to 500 operations.
    if deleted_count > 0 and deleted_count % 500 == 0:
      batch.commit()
      batch = db.batch()

  # Commit any remaining deletions in the last batch.
  if deleted_count % 500 > 0:
    batch.commit()

  print(f"Removed {deleted_count} expired prayer requests.")
