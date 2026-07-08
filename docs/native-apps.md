# Native App Plan (Android / iOS)

Goal: ship Android and iOS apps by wrapping the existing PWA rather than
rebuilding. The site is server-rendered Flask, so the "native app" is a thin
shell around the live site plus native capabilities where they matter.

## Starting position (already in place)

- Valid `manifest.json` (standalone display, icons, theme color, shortcuts).
- Service worker with offline caching and push handling.
- Push notifications already via **FCM** (`/save_fcm_token` backend), which has
  first-class native SDKs on both platforms — the existing token storage
  carries straight over. Messages carry both a `notification` block (so the OS
  displays them for a native shell in the background — data-only messages
  never show natively) and the `data` duplicate that the web service worker
  renders from; native tokens can therefore share the same `fcm_tokens` array
  and send path.
- Firebase Auth session bridge (`/auth/firebase`) — built specifically so a
  native shell can sign in via the native Firebase SDK and exchange the ID
  token for the normal web session. See
  [firebase-auth-migration.md](firebase-auth-migration.md).

## Approaches

| Approach | Platforms | Effort | Notes |
|---|---|---|---|
| **TWA** (Trusted Web Activity, via Bubblewrap/PWABuilder) | Android only | Hours–days | Runs the real PWA in Chrome; push/SW/offline just work. Play Store accepts TWAs readily. |
| **Capacitor** (recommended for both stores) | Android + iOS | ~1–2 weeks | WebView + native plugin bridge; one codebase. Needed for iOS. |
| Hand-built native shells | both | Not worth it | Overkill for a wrapped web app. |

If Android alone is the goal, ship a TWA first — it is nearly free.

## Known blockers and their mitigations

1. **Google OAuth is blocked inside embedded webviews**
   (`disallowed_useragent`). *Mitigation (in progress):* the Firebase Auth
   migration. The native shell signs in with the OS-level Google flow via the
   native Firebase plugin (e.g. `@capacitor-firebase/authentication`), then
   POSTs the ID token to `/auth/firebase`. The web popup flow has the same
   property — sign-in happens outside the webview.

2. **Apple App Store Guideline 4.2** (minimum functionality): Apple rejects
   apps that are "just a website in a wrapper." *Mitigation:* ship genuine
   native value — native push (have it), and candidates like a home-screen
   widget (verse/streak), biometric lock for personal prayers, or share
   extensions. Plan App Review pushback into the iOS timeline. Google Play is
   far more lenient.

3. **iOS web push** only works for home-screen-installed PWAs (16.4+) and is
   less reliable than native APNs; a Capacitor shell using native FCM→APNs is
   the more dependable notification path on iOS.

4. **Apple sign-in requirement**: if the iOS app offers third-party login
   (Google), Apple requires offering **Sign in with Apple** too. Firebase Auth
   supports it as a provider; the `/auth/firebase` bridge handles any Firebase
   provider, but `firebase_auth_logic` matching rules should be reviewed when
   adding it (Apple's email-relay addresses won't match existing doc emails).

## Web APIs already used that map to plugins

`navigator.share`, `navigator.vibrate` (milestone modal) — both have direct
Capacitor plugin equivalents; the web fallbacks keep working inside the shell.

## Sequencing

1. ✅ Firebase Auth phases 1–2 (session bridge + Google sign-in) — shipped to
   prod and proven.
2. 🔄 Firebase Auth phase 3 (email/password) — 3a code merged to `dev`, all
   39 legacy password users imported and the hash mapping canary-verified;
   prod rollout + bake remain, then the 3b cleanup release. After 3a ships,
   the shell never needs the legacy form flows.
3. Android TWA (can ship any time; independent of the shell work).
4. Capacitor shell: native Firebase auth plugin + FCM wiring + iOS native
   value items (remember Sign in with Apple); App Store submission.
