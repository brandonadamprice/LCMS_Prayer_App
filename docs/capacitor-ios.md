# Capacitor iOS: Build & Ship Checklist

iOS sibling of [capacitor-android.md](capacitor-android.md), built for the
headless Mac mini workflow described in
[ios-build-server.md](ios-build-server.md) (read that first — it covers the
machine, the App Store Connect API key, the shared certs repo, and the
`~/.ios-build.env` contract this doc assumes).

The code side is done and lives in this repo:

- `mobile/ios/` — the generated Xcode project (Capacitor 8, Swift Package
  Manager — no CocoaPods). Same remote-URL shell as Android: the WebView
  loads the live site, so web deploys update the app instantly.
- Hand-written native code, mirroring the Android shell:
  - `PrinterPlugin.swift` (registered in `MainViewController.swift`) routes
    the web Print button through `UIPrintInteractionController` — 
    `window.print()` is a no-op in WKWebView too.
  - `AppDelegate.swift` configures Firebase and bridges APNs device tokens
    to **FCM tokens** via `FirebaseMessaging`, so the existing
    `/save_fcm_token` + FCM send path works unchanged on iOS.
  - `App.entitlements` (`aps-environment: production`) and a committed
    shared scheme (`App.xcscheme`) so `xcodebuild` works headlessly.
- `mobile/ios/App/fastlane/` — `bootstrap` / `sync_certs` / `beta` lanes
  (see the Fastfile), all driven by the machine-level env file.
- `.github/workflows/ios-release.yml` — TestFlight release from the GitHub
  UI via the self-hosted runner.

Everything below happens outside the code. Do it in order.

## 1. Register the iOS app in Firebase

1. [Firebase console](https://console.firebase.google.com/) → project
   **lcms-prayer-app** → Project settings → *Your apps* → **Add app** →
   iOS. Bundle ID: **`com.hallowedgains.aswtp`** (must match
   `capacitor.config.json` `appId` and the Xcode project's
   `PRODUCT_BUNDLE_IDENTIFIER` — it does; same ID as Android's package
   name).
2. Download **`GoogleService-Info.plist`** and replace the committed
   placeholder at `mobile/ios/App/App/GoogleService-Info.plist` (the
   placeholder builds but sign-in/push stay broken until replaced). Like
   `google-services.json`, the real file is client config — commit it, and
   expect the same false-positive GitHub secret warning (see the Android
   doc for the key-restriction rationale; restrict the iOS key to the
   bundle ID the same way).
3. Copy the plist's `REVERSED_CLIENT_ID` over the `REPLACE-ME` URL scheme
   in `mobile/ios/App/App/Info.plist` (`CFBundleURLSchemes`) — Google
   sign-in's round-trip back into the app depends on it.

## 2. APNs key (push notifications)

FCM delivers to iOS through APNs, so Firebase needs an APNs auth key:

1. [Apple Developer](https://developer.apple.com/account) → Certificates,
   Identifiers & Profiles → **Keys** → new key with **Apple Push
   Notifications service (APNs)** enabled. Download the `.p8` (one-shot
   download — password manager), note the Key ID.
2. Firebase console → Project settings → **Cloud Messaging** → your iOS
   app → **APNs Authentication Key** → upload it (needs the Key ID and
   Team ID).

No server changes: reminders already send both `notification` and `data`
blocks via FCM, which is exactly what a backgrounded iOS app needs.

## 3. Bootstrap the app with Apple (one-time)

Two halves — the API key covers most of it, but Apple exposes no API for
creating the App Store Connect app entry itself, so that one piece is a
browser step.

1. Over SSH (requires `~/.ios-build.env`, see ios-build-server.md):

   ```bash
   cd mobile/ios/App
   fastlane bootstrap
   ```

   Registers the bundle ID with the Developer Portal (push capability
   enabled) via the API key, then runs `match` to mint the distribution
   cert and provisioning profile into the shared certs repo. Safe to
   re-run; it skips what already exists.

2. In a browser: [App Store Connect](https://appstoreconnect.apple.com) →
   **My Apps** → **+** → **New App**. Platform iOS, name "A Simple Way to
   Pray", primary language English (U.S.), Bundle ID
   `com.hallowedgains.aswtp` (it's in the dropdown thanks to the previous
   step), SKU `com.hallowedgains.aswtp`. Without this entry `fastlane
   beta`'s TestFlight upload has nowhere to land.

## 4. First build → TestFlight

Either over SSH — from `mobile/`: `npm ci && npx cap sync ios`, then
`cd ios/App && fastlane beta` — or from the GitHub UI: **Actions → iOS
Release → Run workflow** (needs the self-hosted runner registered). The
lane pulls certs read-only, sets the build number to TestFlight's latest +
1, builds the IPA, and uploads. Install via the TestFlight app on a real
device.

## 5. Device test checklist

Same list as the Android doc's step 4, with iOS-specific eyes on:

- [ ] **Google sign-in** completes and lands signed in (URL-scheme
      round-trip from step 1.3).
- [ ] Settings → enable notifications: iOS permission prompt appears; a
      test reminder arrives with the app backgrounded **and** killed; tap
      deep-links to the right devotion page. (Push only works on real
      devices, and only after steps 1–2.)
- [ ] **Print button** opens the iOS print sheet ("Save to Files"/AirPrint;
      personal-prayer prompt behaves as on web).
- [ ] External links open Safari, not the WebView; offline error page after
      airplane mode; dark mode.

## 6. App Store review requirements (before submitting past TestFlight)

Apple-specific hurdles Google didn't have — plan these in:

- **Sign in with Apple is mandatory** (Guideline 4.8) because the app
  offers Google sign-in. ✅ Code complete — see the "Sign in with Apple"
  section below for the two one-time console steps and the rebuild.
  TestFlight testing doesn't require it; App Store review does.
- **Guideline 4.2 (minimum functionality)**: expect "it's a website
  wrapper" pushback. Native push, native Google sign-in, and native print
  are the counterargument; have them all working before review, and
  mention them in the Review Notes.
- **Demo account** for the login-gated content: reuse the Play review
  account — its credentials live in Play Console → App content → App
  access (and the password manager), deliberately not in this repo. No
  App Store Connect clicking needed: `fastlane sync_store_listing`
  uploads the App Review contact + demo account from the `REVIEW_*`
  variables in `~/.ios-build.env` (see ios-build-server.md). Keep the
  account's email verified — `/auth/firebase` rejects unverified
  password accounts, which would lock reviewers out.

### The listing itself is in-repo and uploads programmatically

`mobile/ios/App/fastlane/metadata/` (name, subtitle, description, keywords,
categories, URLs — the copy mirrors `store-assets/listing-copy.md`) and
`mobile/ios/App/fastlane/screenshots/en-US/` (same five pages as the Play
set, iPhone 6.9" + iPad 13", regenerated via
`store-assets/capture_ios_screenshots.py`). Upload both with:

```bash
cd mobile/ios/App && fastlane sync_store_listing
```

The app icon needs no upload — App Store Connect takes it from the
uploaded build.

### Questionnaires that must be clicked by hand in App Store Connect

**App Privacy** (App Store Connect → App Privacy) — declare "data is
collected", then (matching the Play Data safety form):

| Data type | Purpose | Linked to identity? | Tracking? |
| --- | --- | --- | --- |
| Contact Info → Email Address | App Functionality | Yes | No |
| User Content → Other User Content (personal prayers, prayer wall) | App Functionality | Yes | No |
| Identifiers → User ID | App Functionality | Yes | No |
| Usage Data → Product Interaction (Google Analytics on the site) | Analytics | No | No |

Plus the standing facts: encrypted in transit, deletable on request.

**Age rating**: answer None to all content questions → 4+. The app is not
a general web browser (it shows only its own site), so "unrestricted web
access" is No.

## Sign in with Apple

Offered **only inside the iOS shell** (native `AuthenticationServices` flow
via the same Firebase plugin as Google) — deliberately not on web/Android,
which would require an Apple Services ID + domain verification for zero
benefit, since Apple only mandates the option where the app runs. What's in
the code: hidden "Sign in/up with Apple" buttons in `signin.html` /
`register.html` that `_firebase_signin.html` reveals in the iOS shell and
wires to `FirebaseAuthentication.signInWithApple()` → the same
`/auth/firebase` bridge; the `com.apple.developer.applesignin` entitlement;
`apple.com` in the plugin's providers; and `firebase_auth_logic.py`
handling for Apple's quirks (relay emails create fresh accounts, shared
real emails link to legacy accounts, missing name claims get a fallback —
all unit-tested).

One-time setup to turn it on:

1. **Firebase console** → Authentication → Sign-in method → **Apple** →
   Enable. Leave the Services ID / OAuth fields empty — they're only for
   web flows, which we don't offer.
2. **On the mini**: `git pull`, then `MATCH_FORCE=1 fastlane bootstrap` —
   the updated bootstrap enables the Sign in with Apple capability on the
   App ID, and `MATCH_FORCE=1` makes match regenerate the provisioning
   profile so it embeds the new entitlement (without it match happily
   serves the stale profile and the build fails signing).
3. `npx cap sync ios` (providers config changed), then `fastlane beta`.

Known-and-accepted UX caveat: an existing Google/email user who signs in
with Apple *and hides their email* gets a fresh empty account — the relay
address is unknowable in advance, so no linking rule can catch it. Signing
in with Apple while sharing the real address links correctly.

## Ongoing

- Web deploys update the app content immediately; a new IPA is only needed
  when `mobile/` changes.
- **Versioning rule** (mirrors CLAUDE.md): a release-worthy `mobile/`
  change bumps Android `versionCode`/`versionName`, `mobile/package.json`
  `version`, **and** `MARKETING_VERSION` in
  `mobile/ios/App/App.xcodeproj/project.pbxproj` — keep all three
  human-facing versions identical. The iOS **build number**
  (`CURRENT_PROJECT_VERSION`) is *not* managed in the repo: the beta lane
  derives it from TestFlight at build time.
- App icon/splash are Capacitor defaults until
  `npx @capacitor/assets generate --ios` is run with real art in
  `mobile/assets/` (same nice-to-have as Android).
