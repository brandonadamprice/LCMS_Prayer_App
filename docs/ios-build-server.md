# iOS Build Server (Mac mini) — Shared Hallowed Gains Infrastructure

This doc describes the **shared, project-agnostic** iOS release
infrastructure: one Mac mini builds and ships every Hallowed Gains iOS app
headlessly (SSH / CI only — no screen sharing, no Xcode GUI). This is the
canonical copy; mirror it — together with
[apple-release-playbook.md](apple-release-playbook.md), the Apple-side
process knowledge and traps — into `Hallowed-Gains-LLC/ios-certs` so every
project's contributors find them (commands at the bottom of the playbook).
App-specific release steps live in each app repo.

Apps on this infrastructure, and where their per-app steps live:

| App | Framework | Per-app doc |
| --- | --- | --- |
| A Simple Way to Pray | Capacitor (web shell) | [capacitor-ios.md](capacitor-ios.md) |
| Idle Bible | Flutter (native game) | `Docs/iOS_Release.md` in `Hallowed-Gains-LLC/Idle-Bible` |

The framework column is the only thing that differs. Everything below —
the machine, the API key, the certs repo, the env file, the runner — is
identical for both, which is the whole point.

## The machine

Mac mini ("Brandons-Mac-mini"), reachable over SSH (Tailscale). One-time
setup already done:

- **Remote Login** (SSH) enabled; **Tailscale** installed for
  access from anywhere without port forwarding.
- **Automatic login** enabled for the build user — after a reboot the login
  keychain (which holds signing certs for manual SSH builds) is unlocked
  without a GUI session. CI builds don't even need this: the fastlane lanes
  run `setup_ci` under CI and use a throwaway keychain.
- Never sleeps, restarts after power failure:
  `sudo pmset -a sleep 0 autorestart 1`.
- Toolchain via Homebrew: `node`, `fastlane`, `cocoapods` (not needed by
  Capacitor 8's SPM projects, kept for anything older), and
  `xcodesorg/made/xcodes` (headless Xcode installs/updates:
  `xcodes install --latest`).
- Full Xcode installed, license accepted
  (`sudo xcodebuild -license accept`, `sudo xcodebuild -runFirstLaunch`).

Maintenance without the GUI: `softwareupdate -ia --restart` for macOS point
updates; `xcodes` for Xcode. Chrome Remote Desktop remains break-glass only.

## Shared account-level pieces (all apps, one Apple team)

| Piece | Where it lives |
| --- | --- |
| **App Store Connect API key** (`.p8`) | Master copy in the password manager (with Key ID + Issuer ID); working copy on the mini at `~/.appstoreconnect/private_keys/AuthKey_<KEYID>.p8`, `chmod 600`. Never in any repo. Revoke in App Store Connect if the machine is ever compromised. |
| **Signing certs + provisioning profiles** | Encrypted by fastlane match in the private repo `Hallowed-Gains-LLC/ios-certs`. One repo serves every app on the Apple team, regardless of which GitHub owner hosts the app's code. |
| **Certs repo access** | A write-enabled **deploy key** on `ios-certs` whose private half is `~/.ssh/match_deploy_key` on the mini, routed via the `github.com-certs` alias in `~/.ssh/config` (`IdentitiesOnly yes`), so the key is never offered to other repos. |
| **Match passphrase** | Password manager + `MATCH_PASSWORD` in the env file below. Repo access + passphrase = the team's signing identity; keep both tight. |

## The `~/.ios-build.env` contract

Every app's Fastfile loads `~/.ios-build.env` from the build user's home
(variables already present in the environment win, so CI can override).
This file is the single machine-level configuration point — a new app needs
**nothing** added here. Contents (values live only on the mini and in the
password manager):

```bash
APPLE_TEAM_ID=XXXXXXXXXX                 # developer.apple.com → Membership
APP_STORE_CONNECT_KEY_ID=XXXXXXXXXX
APP_STORE_CONNECT_ISSUER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
APP_STORE_CONNECT_KEY_PATH=/Users/<user>/.appstoreconnect/private_keys/AuthKey_XXXXXXXXXX.p8
MATCH_GIT_URL=git@github.com-certs:Hallowed-Gains-LLC/ios-certs.git
MATCH_PASSWORD=<match passphrase>
MATCH_KEYCHAIN_PASSWORD=<macOS login password of the build user>
REVIEW_CONTACT_PHONE=<intl format, e.g. +1 555 555 5555>
REVIEW_CONTACT_EMAIL=<App Review contact email>
REVIEW_DEMO_USER=<review demo account email>
REVIEW_DEMO_PASSWORD=<review demo account password>
# Optional: REVIEW_CONTACT_FIRST_NAME / REVIEW_CONTACT_LAST_NAME override
# the committed defaults (Brandon Price) in the app's Fastfile.
```

`chmod 600 ~/.ios-build.env`. Because the Fastfile reads this file itself,
it works identically for an interactive SSH session and for the GitHub
Actions runner service (which has no login-shell environment).

The `REVIEW_*` block feeds `fastlane sync_store_listing`: App Review
contact info and the review demo account (per-app values can override the
machine file via a gitignored `fastlane/.env` next to the app's Fastfile —
fastlane loads it automatically). Supplying them also works around a
deliver crash on brand-new apps (fastlane#20538).

`MATCH_KEYCHAIN_PASSWORD` exists because SSH sessions see the login
keychain **locked** and macOS cannot show its unlock dialog there — cert
import and codesigning fail with "User interaction is not allowed". The
lanes' `prepare_keychain` step unlocks the login keychain with it before
match touches anything (and match reuses the same variable for the
key-partition-list step). CI runs skip all of this: `setup_ci` gives the
runner a throwaway keychain. Verify the password is the right one with
`security unlock-keychain ~/Library/Keychains/login.keychain-db` (prompts
once; silence means success) — if the macOS login password fails there,
the keychain's own password has drifted from the account password and
needs `security set-keychain-password` first.

## Self-hosted GitHub Actions runner

The end state: releases trigger from the GitHub UI (or a phone), and nobody
SSHes anywhere. Per app repo:

1. Repo → Settings → Actions → Runners → **New self-hosted runner** →
   macOS/arm64, and follow the download/config commands over SSH on the
   mini. Use a separate runner directory per repo (e.g.
   `~/actions-runner/<repo>`).
2. Install it as a service so it survives reboots:
   `./svc.sh install && ./svc.sh start`.
3. The repo's workflow targets `runs-on: [self-hosted, macOS]` (see
   `.github/workflows/ios-release.yml` in this repo for the template) and
   just runs the app's fastlane lane; all secrets come from the machine, so
   **no GitHub Actions secrets are needed** and the API key never leaves
   the mini.

## Adopting this setup in a new app repo

The per-app surface is deliberately tiny:

1. An iOS Xcode project in the repo (`npx cap add ios` for Capacitor,
   `flutter create --platforms=ios` for Flutter), with a **shared Xcode
   scheme committed** (`<Project>.xcodeproj/xcshareddata/xcschemes/`) —
   xcodebuild can't build schemes that only exist in someone's GUI session.
2. Copy a fastlane folder (Appfile, Matchfile, Fastfile) from whichever
   existing app matches your framework — `mobile/ios/App/fastlane/` here,
   `app/ios/fastlane/` in Idle-Bible; change the Appfile `app_identifier`
   and the Fastfile `APP_NAME`/`XCODEPROJ`/`SCHEME`. **The Matchfile and
   the env contract need no changes — that's the point.** Only the `beta`
   lane's build step is framework-specific:
   - *Capacitor*: `npm ci && npx cap sync ios`, then gym archives the
     project directly.
   - *Flutter*: run `flutter build ios --release --config-only` first. It
     writes `Flutter/Generated.xcconfig` (where `CFBundleVersion`'s
     `$(FLUTTER_BUILD_NUMBER)` comes from) and runs `pod install`, then
     stops before compiling — so gym's archive does the Dart and Xcode
     work exactly once. Archive from the **workspace**, not the project:
     the Pods project only exists in the workspace. There is no
     `MARKETING_VERSION` to read either — the version comes from
     `pubspec.yaml`.
3. Copy `.github/workflows/ios-release.yml`; register a runner for the repo
   (section above). Flutter repos add a `subosito/flutter-action@v2` step
   so the mini needs no per-app toolchain.
4. One-time, over SSH from the directory holding `fastlane/`: `fastlane
   bootstrap` — registers the bundle ID via the API key, enables the
   capabilities that app actually needs, and generates certs/profiles into
   the shared certs repo. Then create the App Store Connect app entry in
   the browser (My Apps → + → New App, picking that bundle ID) — Apple has
   no API for that one step, and fastlane's `produce` only supports
   interactive Apple ID login. Subsequent releases are `fastlane beta` or
   the workflow button.
5. The store listing: write the app's `fastlane/metadata/` texts, capture
   screenshots at the required sizes (script pattern:
   `store-assets/capture_ios_screenshots.py`), and upload everything with
   `fastlane sync_store_listing`. TestFlight mechanics, review gates, and
   the traps already hit once:
   [apple-release-playbook.md](apple-release-playbook.md).

**Capabilities are per-app, so copy the `bootstrap` lane's capability block
deliberately rather than wholesale.** Push notifications are the example:
the prayer app enables them because its reminders arrive via FCM/APNs,
while Idle Bible's are *local* notifications scheduled on the device — it
enables Sign in with Apple and nothing else, and needs no APNs key at all.
An unused capability means a provisioning profile claiming an entitlement
the binary never uses.

> **After changing any App ID capability, re-run with `MATCH_FORCE=1`.**
> match does not notice that the App ID changed, and will keep serving the
> previously generated profile — which lacks the new entitlement, so the
> feature fails at runtime with nothing in the build log to explain it.

Certificates are team-level: the first app's `bootstrap` created the Apple
Distribution cert, and every later app's `match` run reuses it, adding only
its own provisioning profile to the certs repo.
