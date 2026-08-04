#!/usr/bin/env python3
"""Publish the rendered Instagram creative to Google Drive.

Drive is the home for the rendered ads — the repo keeps only the sources
(HTML/CSS, fonts, render.js, ad_copy.md), so the binaries never land in git.
After rendering, publish with:

    NODE_PATH=$(npm root -g) node render.js
    python3 sync_drive.py                # add --dry-run to see the plan first

Files are matched by name inside the target folder: an existing file is
updated in place (so Drive links stay stable and shared links keep working),
anything new is created.

Auth — application-default credentials with the Drive scope added:

    gcloud auth application-default login \\
        --scopes=openid,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/cloud-platform

Deps (deliberately not in devotions/requirements.txt — this is a marketing
tool, not part of the app):

    pip install google-api-python-client google-auth
"""
import argparse
import mimetypes
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
INSTAGRAM = os.path.dirname(HERE)

# Drive: My Drive / Hallowed Gains / A Simple Way To Pray / Social Media / Instagram
FOLDER_INSTAGRAM = "1G8dcPDklGEX9el93Xdc77nzGM0xGX9W-"
FOLDER_STILLS = "1OTlMGCXFeXOCLAMV3TZNQc4Mfn3xmEZj"
FOLDER_REELS = "1ixRlrfAgIDwsCYT41NPwTGeEzB9iRG25"

# (local path relative to marketing/instagram, destination Drive folder)
TARGETS = [
    ("stills", FOLDER_STILLS),
    ("reels", FOLDER_REELS),
]
LOOSE_FILES = [
    ("ad_copy.md", FOLDER_INSTAGRAM),
]

SCOPES = ["https://www.googleapis.com/auth/drive"]


def build_service():
    try:
        import google.auth
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit(
            "Missing deps. Install them with:\n"
            "    pip install google-api-python-client google-auth"
        )

    try:
        creds, _ = google.auth.default(scopes=SCOPES)
    except Exception as exc:  # no ADC at all
        sys.exit(
            f"No application-default credentials ({exc}).\n"
            "Run: gcloud auth application-default login --scopes=openid,"
            "https://www.googleapis.com/auth/drive,"
            "https://www.googleapis.com/auth/cloud-platform"
        )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def find_existing(service, folder_id, name):
    """Return the id of a non-trashed file called `name` in `folder_id`."""
    escaped = name.replace("\\", "\\\\").replace("'", "\\'")
    resp = (
        service.files()
        .list(
            q=f"'{folder_id}' in parents and name = '{escaped}' and trashed = false",
            fields="files(id, name)",
            pageSize=2,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def upload(service, path, folder_id, dry_run):
    name = os.path.basename(path)
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    size_mb = os.path.getsize(path) / 1e6

    if dry_run:
        print(f"  would upload {name} ({size_mb:.1f} MB, {mime})")
        return

    from googleapiclient.http import MediaFileUpload

    existing = find_existing(service, folder_id, name)
    media = MediaFileUpload(path, mimetype=mime, resumable=True)

    if existing:
        f = (
            service.files()
            .update(fileId=existing, media_body=media, fields="id, webViewLink",
                    supportsAllDrives=True)
            .execute()
        )
        verb = "updated"
    else:
        f = (
            service.files()
            .create(
                body={"name": name, "parents": [folder_id]},
                media_body=media,
                fields="id, webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
        verb = "created"

    print(f"  {verb} {name} ({size_mb:.1f} MB) → {f['webViewLink']}")


def collect(local_dir):
    """Rendered output only — skip dotfiles and anything the renderer left behind."""
    if not os.path.isdir(local_dir):
        return []
    return [
        os.path.join(local_dir, n)
        for n in sorted(os.listdir(local_dir))
        if not n.startswith(".") and os.path.isfile(os.path.join(local_dir, n))
    ]


def git(*args, cwd=INSTAGRAM):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True
    ).stdout


def collect_from_git(ref, rel, stage):
    """Materialize `rel` as of `ref` into `stage/`, for publishing without a re-render.

    The rendered assets were removed from git once Drive became their home, so
    `--from-git <ref-before-that>` is how you republish them later.
    """
    # git resolves both pathspecs and `ref:path` against the cwd, so pin
    # everything to the repo root and keep the paths root-relative.
    root = git("rev-parse", "--show-toplevel").decode().strip()
    prefix = os.path.relpath(os.path.join(INSTAGRAM, rel), root)
    listing = git("ls-tree", "-r", "--name-only", "-z", ref, "--", prefix, cwd=root)

    paths = []
    for tracked in listing.decode().split("\0"):
        if not tracked:
            continue
        name = os.path.basename(tracked)
        if name.startswith("."):
            continue
        out = os.path.join(stage, name)
        with open(out, "wb") as fh:
            fh.write(git("show", f"{ref}:{tracked}", cwd=root))
        paths.append(out)
    return sorted(paths)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="list what would upload")
    ap.add_argument(
        "--from-git",
        metavar="REF",
        help="publish the rendered assets as they were at REF instead of the "
        "working tree (e.g. the commit before they were removed from git)",
    )
    args = ap.parse_args()

    with tempfile.TemporaryDirectory(prefix="ig-sync-") as stage:
        plan = []
        for rel, folder_id in TARGETS:
            if args.from_git:
                sub = os.path.join(stage, rel)
                os.makedirs(sub, exist_ok=True)
                files = collect_from_git(args.from_git, rel, sub)
                miss = f"{rel}/: nothing at {args.from_git}"
            else:
                files = collect(os.path.join(INSTAGRAM, rel))
                miss = f"{rel}/: nothing rendered — run render.js first"
            if not files:
                print(miss, file=sys.stderr)
            plan.append((rel, folder_id, files))

        for rel, folder_id in LOOSE_FILES:
            path = os.path.join(INSTAGRAM, rel)
            plan.append((rel, folder_id, [path] if os.path.isfile(path) else []))

        if not any(files for _, _, files in plan):
            sys.exit("Nothing to upload.")

        service = None if args.dry_run else build_service()

        for rel, folder_id, files in plan:
            if not files:
                continue
            print(f"{rel} → https://drive.google.com/drive/folders/{folder_id}")
            for path in files:
                upload(service, path, folder_id, args.dry_run)


if __name__ == "__main__":
    main()
