# Apple Release Playbook — Hallowed Gains (all apps)

Generic, app-agnostic knowledge for shipping iOS apps through the shared
build server. Companion to [ios-build-server.md](ios-build-server.md)
(machine + env setup); this doc is the Apple-side process and the traps
already hit once so no app hits them twice. Canonical copy lives in the
prayer-app repo; mirror both docs into `Hallowed-Gains-LLC/ios-certs`
(commands at the bottom).

## What the API key can and cannot do

Everything in the pipeline authenticates with the App Store Connect API
key — no Apple ID login, no 2FA — **except** the operations Apple simply
doesn't expose:

| Works headless via API | Website-only (browser, one-time per app) |
| --- | --- |
| Register bundle ID + capabilities (`bootstrap` lane) | Create the App Store Connect **app entry** (My Apps → + → New App) |
| Signing certs + profiles (match) | App Privacy questionnaire |
| Build upload + TestFlight (`beta` lane) | Age rating questionnaire |
| Listing metadata, screenshots, review contact + demo account (`sync_store_listing` lane) | Creating TestFlight groups / submitting for beta review |

Do not use fastlane `produce`/`create_app_online` — it only supports
interactive Apple ID login and will fail with the API key.

## Keys and certificates (account-level facts)

- **App Store Connect API key**: download is one-shot → password manager.
  App Manager role. Revoke from ASC if the build server is ever
  compromised.
- **APNs auth key**: choose **Team scoped** (works for every app) and
  **Sandbox & Production** — a Sandbox-only key silently breaks push for
  TestFlight/App Store builds. One-shot download. Max **2** active APNs
  keys per team. Upload once per Firebase project (Project settings →
  Cloud Messaging).
- **Apple Distribution certificates**: max **3** per team, and they're
  team-level — one cert signs every app; match reuses it. A failed match
  run can strand an orphan cert on the portal (created, private key lost):
  revoke orphans at developer.apple.com → Certificates, or you'll hit the
  cap.
- Keychain-over-SSH and `MATCH_KEYCHAIN_PASSWORD`: see ios-build-server.md.

## Per-app conventions

- **Info.plist**: set `ITSAppUsesNonExemptEncryption` to `false` for
  HTTPS-only apps — kills the export-compliance prompt on every upload.
- **Build number** (`CFBundleVersion`): never managed in the repo; the
  `beta` lane sets it to TestFlight's latest + 1, so re-runs never collide.
  `MARKETING_VERSION` is the human version and lives in the repo.
- **`sync_store_listing` must include `app_review_information`** — besides
  filling review contact + demo account, it works around a deliver crash
  on brand-new apps (fastlane#20538: the version has no App Review detail
  record until review info creates it; deliver's attachment step raises
  "No data" on the empty response).
- **Demo review account**: created through the app's normal signup, email
  verified (unverified accounts get rejected by auth bridges and lock
  reviewers out), stored only in the password manager / env — never in a
  repo. Reused for both Play and App Store review.
- **Screenshots**: only two sets are required — iPhone 6.9" (1320×2868)
  and, if the app targets iPad, iPad 13" (2064×2752). For web-shell apps,
  capture the real site with Playwright at those exact pixel sizes
  (viewport ÷ scale factor; script pattern:
  `mobile/store-assets/capture_ios_screenshots.py` in the prayer-app
  repo). The listing icon comes from the uploaded build — nothing to
  upload.

## TestFlight

- **Internal testers** (ASC users on the team): no review, instant, but
  each needs an iPhone and an ASC account.
- **External testers**: require **Beta App Review**, which does NOT start
  when the build uploads — it starts when you create an external group,
  add the build, and click Submit for Review (few hours to ~2 days for a
  first app). Then enable the group's **public link**: one URL, no email
  invites, up to 10,000 testers.
- Beta review is lighter than App Store review: **Sign in with Apple is
  not required for TestFlight**, and Guideline 4.2 is rarely enforced
  there. It does use the demo account — verify it logs in before
  submitting.
- No iPhone on hand? The iOS Simulator on the build server covers
  everything except real push; recruit one real-device tester to confirm
  notifications arrive with the app killed.

## App Store submission gates (beyond TestFlight)

- **Sign in with Apple is mandatory** the moment the app offers any
  third-party login (Google, Facebook, …). Plan the auth work before the
  submission, not after the rejection. Cost-saver: offer it **natively in
  the shell only** — Apple only mandates it where the app runs, and the
  native flow needs no Services ID, no key, and no domain verification;
  the Firebase console just needs the Apple provider toggled on. After
  enabling the App ID capability, regenerate the provisioning profile
  (`MATCH_FORCE=1` — match won't notice the App ID changed and keeps
  serving the stale profile). Relay-email caveat: a hidden address can
  never match an existing account, so returning users should sign in the
  way they signed up.
- **Guideline 4.2 (minimum functionality)** for web-shell apps: expect
  "it's a website wrapper" pushback. Counter with genuine native value —
  native push, OS-level sign-in, native print/share/widgets — working at
  review time and listed in the Review Notes (the `sync_store_listing`
  lane sets these).
- Hand-clicked once per app: App Privacy (declare what the backend
  actually stores: typically email + user content + user ID linked to
  identity for App Functionality; analytics usage data unlinked; no
  tracking) and the age rating questionnaire ("unrestricted web access"
  is No for a shell that shows only its own site — it is not a browser).
- Privacy policy URL is required — host it on the app's own site.

## Mirroring these docs into ios-certs

From any machine with certs-repo access (the build server qualifies):

```bash
cd ~/ios-certs && git pull
curl -o README.md   https://raw.githubusercontent.com/brandonadamprice/LCMS_Prayer_App/main/docs/ios-build-server.md
curl -o PLAYBOOK.md https://raw.githubusercontent.com/brandonadamprice/LCMS_Prayer_App/main/docs/apple-release-playbook.md
git add -A && git commit -m "Sync shared iOS docs" && git push
```

Re-run whenever the canonical docs change.
