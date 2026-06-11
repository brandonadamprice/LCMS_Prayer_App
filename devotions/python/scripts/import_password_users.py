"""Batch-imports legacy email/password users into Firebase Authentication.

Phase 3a of docs/firebase-auth-migration.md. For every user doc that has a
password_hash, no firebase_uid, and an email, this:

  1. creates a Firebase Auth user via importUsers with
       - uid = the Firestore doc ID (so firebase_uid matching is exact),
       - the user's existing werkzeug hash (scrypt -> STANDARD_SCRYPT,
         pbkdf2:sha256 <= 120k rounds -> PBKDF2_SHA256), so passwords carry
         over unchanged -- no resets;
  2. (on success) writes firebase_uid = doc ID back onto the Firestore doc.

Docs that are already firebase-linked, have no email, or hold a
non-importable hash are skipped and reported. The Firestore doc's
password_hash is NOT touched (deferred delete -- see the migration doc).

SAFETY MODEL
  - Default is a DRY RUN: prints the full plan, writes nothing anywhere.
  - --execute performs the import (and the firebase_uid backfill writes).
  - --uid DOC_ID restricts the run to one user: ALWAYS canary-test first --
    import a single test account with --uid, then verify you can sign in
    through Firebase with its known password BEFORE the bulk run. This
    proves the scrypt parameter mapping end-to-end; if the canary cannot
    sign in, delete that one user in the Firebase console, fix, re-run.
  - A failed/wrong import is recoverable: legacy login still works (3a keeps
    it), and Firebase users can be deleted and re-imported.

PREREQUISITES
  - Email/Password provider ENABLED in Firebase console (Authentication ->
    Sign-in method), with "one account per email" (the default) -- this is
    also what makes a later Google sign-in by the same email link onto the
    imported account instead of creating a duplicate.
  - GCP application-default credentials, same as the audit script.

Run from devotions/python:

    python scripts/import_password_users.py                # dry run
    python scripts/import_password_users.py --uid <doc-id> --execute  # canary
    python scripts/import_password_users.py --execute      # bulk
"""

import argparse
import collections
import os
import sys

# Allow running as `python scripts/import_password_users.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firebase_admin  # pylint: disable=wrong-import-position
from firebase_admin import auth as fb_auth  # pylint: disable=wrong-import-position
import password_hash_logic  # pylint: disable=wrong-import-position
import utils  # pylint: disable=wrong-import-position

try:
  firebase_admin.get_app()
except ValueError:
  firebase_admin.initialize_app(options={"projectId": "lcms-prayer-app"})

# importUsers accepts at most 1000 records per call.
_BATCH_LIMIT = 1000

_PLAN_FIELDS = ["password_hash", "firebase_uid", "email", "name"]


def _hash_alg_for(scheme, params, key_hex):
  """Maps a werkzeug hash family onto a firebase_admin UserImportHash.

  NOTE on STANDARD_SCRYPT: memory_cost is passed as the raw scrypt N
  (werkzeug's 32768), block_size as r, parallelization as p. This mapping is
  exactly what the canary run exists to prove -- do not bulk-run before a
  canary sign-in has succeeded.
  """
  if scheme == password_hash_logic.SCHEME_SCRYPT:
    n, r, p = params
    return fb_auth.UserImportHash.standard_scrypt(
        memory_cost=n,
        block_size=r,
        parallelization=p,
        derived_key_length=len(key_hex) // 2,
    )
  if scheme == password_hash_logic.SCHEME_PBKDF2_SHA256:
    (rounds,) = params
    return fb_auth.UserImportHash.pbkdf2_sha256(rounds=rounds)
  raise ValueError(f"no Firebase mapping for scheme {scheme!r}")


def _build_plans(db, only_uid=None):
  """Streams user docs and returns (plans, skips)."""
  plans, skips = [], []
  query = db.collection("users").select(_PLAN_FIELDS)
  for doc in query.stream():
    if only_uid and doc.id != only_uid:
      continue
    fields = doc.to_dict() or {}
    if not fields.get("password_hash"):
      continue  # Not a password user; not part of this migration.
    plan, skip_reason = password_hash_logic.build_import_plan(doc.id, fields)
    if plan:
      plans.append(plan)
    else:
      skips.append((doc.id, skip_reason))
  return plans, skips


def _import_group(db, scheme, params, group):
  """Imports one same-parameters group and backfills firebase_uid."""
  records = [
      fb_auth.ImportUserRecord(
          uid=plan["uid"],
          email=plan["email"],
          email_verified=plan["email_verified"],
          display_name=plan["display_name"],
          password_hash=bytes.fromhex(plan["key_hex"]),
          password_salt=plan["salt"].encode("utf-8"),
      )
      for plan in group
  ]
  hash_alg = _hash_alg_for(scheme, params, group[0]["key_hex"])

  imported, failed = 0, 0
  for start in range(0, len(records), _BATCH_LIMIT):
    batch_records = records[start : start + _BATCH_LIMIT]
    batch_plans = group[start : start + _BATCH_LIMIT]
    result = fb_auth.import_users(batch_records, hash_alg=hash_alg)
    failed_indexes = set()
    for err in result.errors:
      failed_indexes.add(err.index)
      print(f"  IMPORT FAILED uid={batch_plans[err.index]['uid']}: {err.reason}")

    # Backfill firebase_uid only for records Firebase actually accepted.
    write_batch = db.batch()
    for i, plan in enumerate(batch_plans):
      if i in failed_indexes:
        continue
      write_batch.set(
          db.collection("users").document(plan["uid"]),
          {"firebase_uid": plan["uid"]},
          merge=True,
      )
    write_batch.commit()
    imported += result.success_count
    failed += result.failure_count
  return imported, failed


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
      "--execute", action="store_true",
      help="actually import and write firebase_uid (default: dry run)",
  )
  parser.add_argument(
      "--uid", default=None,
      help="restrict to a single user doc ID (canary run)",
  )
  args = parser.parse_args()

  db = utils.get_db_client()
  plans, skips = _build_plans(db, only_uid=args.uid)

  groups = collections.defaultdict(list)
  for plan in plans:
    groups[(plan["scheme"], plan["params"])].append(plan)

  mode = "EXECUTE" if args.execute else "DRY RUN"
  print(f"\n=== Password-user import ({mode}) ===\n")
  print(f"To import: {len(plans)} users")
  for (scheme, params), group in groups.items():
    label = scheme + ":" + ":".join(str(p) for p in params)
    print(f"  {len(group):5d}  {label}")
    for plan in group:
      print(f"         uid={plan['uid']}  email={plan['email']}")
  print(f"\nSkipped: {len(skips)}")
  for doc_id, reason in skips:
    print(f"  {doc_id}: {reason}")

  if not args.execute:
    print("\nDry run only -- nothing was imported or written.")
    print("Canary first: rerun with --uid <test-account-doc-id> --execute,")
    print("verify that account can sign in via Firebase, THEN bulk --execute.")
    return

  if not plans:
    print("\nNothing to import.")
    return

  total_imported = total_failed = 0
  for (scheme, params), group in groups.items():
    imported, failed = _import_group(db, scheme, params, group)
    total_imported += imported
    total_failed += failed
  print(
      f"\nDone: {total_imported} imported (firebase_uid backfilled),"
      f" {total_failed} failed."
  )


if __name__ == "__main__":
  main()
