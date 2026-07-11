# Capacitor Android: Build & Ship Checklist

The code side is done and lives in this repo:

- `mobile/` — the Capacitor project. `capacitor.config.json` points the
  WebView at the live site (`https://asimplewaytopray.com`), so the app has
  no bundled web code; web deploys update the app instantly with no store
  release. `mobile/android/` is the generated native project (near-zero
  hand-written code; `MainActivity.java` is 5 generated lines).
- Plugins installed: `@capacitor-firebase/authentication` (OS-level Google
  sign-in → `/auth/firebase` bridge) and `@capacitor/push-notifications`
  (native FCM token → `/save_fcm_token`, tap deep-links).
- Web-side wiring (ships with the Flask app; inert in normal browsers):
  `static/app.js` (shell detection, token registration/rotation, tap
  deep-link, foreground toast), `settings.html` (notification toggle native
  path), `_firebase_signin.html` (native Google sign-in path).

Everything below happens **outside the code** — console dashboards, keys,
and the store. Do them in order.

## 1. Register the Android app in Firebase

1. [Firebase console](https://console.firebase.google.com/) → project
   **lcms-prayer-app** → Project settings → *Your apps* → **Add app** →
   Android.
2. Package name: **`com.hallowedgains.aswtp`** — must match exactly what
   the repo uses (`mobile/capacitor.config.json` `appId`,
   `mobile/android/app/build.gradle` `namespace`/`applicationId`,
   `MainActivity.java`'s package). ✅ Done 2026-07 — registered in Firebase
   and the repo renamed to match. The ID is permanent once the app is on
   Google Play.
3. Download **`google-services.json`** and put it at
   `mobile/android/app/google-services.json`, then commit it (it's client
   config — IDs, not secrets; same class of values `/auth/firebase_config`
   already serves publicly, and every shipped APK embeds the same file).
   The Gradle build auto-detects it; Google sign-in and push both stay
   broken until this file is in place.

   **Expect a GitHub "secret detected" warning** — the scanner
   pattern-matches the `AIza…` API key without knowing it's a Firebase
   *client* key. It's a false positive; bypass/dismiss it as such. The real
   protection is key restriction, not secrecy: in Google Cloud console →
   APIs & Services → Credentials, edit **"Android key (auto created by
   Firebase)"** → Application restrictions → Android apps → add
   `com.hallowedgains.aswtp` + the SHA-1s from step 2. Then the key only
   works from the signed app, no matter who copies it.

## 2. Add SHA fingerprints (required for Google sign-in)

Native Google sign-in only works for APK signatures Firebase knows about.

1. Get the debug key's fingerprints (the debug keystore is created
   automatically the first time Android Studio builds the app — so install
   Android Studio / do step 3's first build before this). Easiest path, no
   `keytool` needed: in Android Studio open the Gradle panel (right edge) →
   `app` → Tasks → android → **signingReport**, and read SHA1/SHA-256 for
   the `debug` variant from the output. Terminal equivalent from
   `mobile/android/`: `./gradlew signingReport` (`gradlew.bat` on Windows).

   If you'd rather use `keytool`: it ships inside a JDK, not standalone,
   which is why a bare terminal says "keytool not found". Use Android
   Studio's bundled one:

   - **Windows**: `"C:\Program Files\Android\Android Studio\jbr\bin\keytool.exe" -list -v -alias androiddebugkey -keystore "%USERPROFILE%\.android\debug.keystore" -storepass android`
   - **macOS**: `"/Applications/Android Studio.app/Contents/jbr/Contents/Home/bin/keytool" -list -v -alias androiddebugkey -keystore ~/.android/debug.keystore -storepass android`
   - **Linux**: `<android-studio>/jbr/bin/keytool` with the same arguments.

2. Firebase console → Project settings → your Android app → **Add
   fingerprint** → paste the SHA-1 and SHA-256.
3. **Re-download `google-services.json`** afterwards (it now embeds the
   OAuth client) and replace the one in the repo.
4. Repeat this step later for the **Play App Signing** key (step 6) — sign-in
   works on your device but fails for Play-installed users until you do.

Prerequisite that's already true: the Google provider is enabled in
Firebase Authentication (the web sign-in uses it).

## 3. Build and run locally

1. Install [Android Studio](https://developer.android.com/studio) (bundles
   the SDK and JDK).
2. From `mobile/`: `npm install`, then `npx cap sync android`, then
   `npx cap open android` (opens Android Studio).
3. Run on an emulator or a USB-connected phone (enable Developer options →
   USB debugging). First Gradle sync downloads dependencies; be patient.

## 4. Device test checklist

- [ ] App opens to the live site; navigation, offline page after airplane
      mode, dark mode all behave.
- [ ] **Google sign-in**: OS account chooser appears (no browser redirect),
      lands signed in. Backing out of the chooser just resets the button.
- [ ] **Email sign-in** (Firebase web SDK — works in the WebView unchanged).
- [ ] Settings → enable notifications: Android 13+ system permission prompt
      appears; toggle sticks.
- [ ] Send a test reminder (`/settings` → reminders): notification appears
      with the app **backgrounded and killed**; tapping it opens the right
      devotion page (the `url` deep link).
- [ ] Foreground push shows the toast.
- [ ] External links (e.g. ESV copyright link) open in the browser, not the
      WebView.

## 5. Release build & Google Play

1. [Play Console](https://play.google.com/console) developer account
   ($25 one-time, individual is fine).
2. Create app → accept **Play App Signing** (Google holds the final signing
   key; you only manage an *upload* key). Create the upload keystore inside
   Android Studio — Build → **Generate Signed App Bundle / APK** → Create
   new… (no `keytool` needed; if you prefer the CLI, use the bundled
   `keytool` paths from step 2 with
   `-genkey -v -keystore upload-keystore.jks -alias upload -keyalg RSA -keysize 2048 -validity 10000`).
   Keep the keystore + passwords somewhere safe and **out of the repo**.
3. Build an **AAB** (Android App Bundle), upload to an **Internal testing**
   track first, install via the opt-in link on a real phone, re-run the
   step 4 checklist on that build.
4. **App access test account** (required — the app has login-gated
   functionality, so review needs a demo login):
   - Register a dedicated account through the site's normal sign-up (e.g.
     `playreview@…`) with a strong, unique password.
   - **Verify its email before submitting** — the `/auth/firebase` bridge
     rejects unverified password accounts (`403 email_unverified`), which
     would lock the reviewer out.
   - Sign in once in the built app to confirm it works.
   - Enter the credentials ONLY in Play Console → App content → **App
     access** (visible to Google's review team only). ⚠️ Never commit the
     real credentials anywhere in this repo — it is public, and unlike the
     Firebase client config a password is a true secret.
5. Store listing chores before production rollout: app name, short/full
   description, screenshots (phone + 7" tablet), 512×512 icon, feature
   graphic, **privacy policy URL** (required — host one on the site),
   Data safety form (declare: account data/email collected, encrypted in
   transit, deletable; push tokens), content rating questionnaire, target
   audience. Budget an afternoon.

## 6. After the first Play upload

Play Console → your app → Setup → **App integrity** → copy the *App signing
key* SHA-1 and SHA-256 → add both as fingerprints in Firebase (step 2) →
re-download and commit `google-services.json`. Without this, Google sign-in
fails on Play-installed builds even though your local build works.

## Troubleshooting

- **Build fails with `JdkImageTransform` / `jlink.exe` /
  `androidJdkImage`** (often mentioning a `C:\Program Files\Java\jdk-XX`
  path): Gradle picked up a system JDK that's newer than the Android
  Gradle Plugin supports. The build needs **JDK 21** — Android Studio
  bundles it. Fix in Android Studio: Settings → Build, Execution,
  Deployment → Build Tools → Gradle → **Gradle JDK** → the bundled
  `jbr-21` ("Embedded JDK"). For terminal builds, put
  `org.gradle.java.home=C:/Program Files/Android/Android Studio/jbr`
  in `%USERPROFILE%\.gradle\gradle.properties` (macOS:
  `/Applications/Android Studio.app/Contents/jbr/Contents/Home`), run
  `gradlew --stop` to kill the old daemon, and rebuild. Don't uninstall
  the newer JDK — just keep Gradle off it.

- **Warning: "Using flatDir should be avoided…"** — harmless, present in
  every Capacitor project. The generated `capacitor-cordova-android-plugins`
  module declares a `flatDir` repo for Cordova plugin `.aar`s; we have no
  Cordova plugins, so it resolves nothing. Don't patch the file — `npx cap
  sync` regenerates it.

## App Links (site links open in the app)

The pieces are in place — manifest `autoVerify` intent filter for the apex
domain, `/.well-known/assetlinks.json` route, and the in-app deep-link
handler in `app.js`. What remains is YOUR fingerprints (verification fails
harmlessly until then; links just keep opening in the browser):

1. Edit `devotions/static/well-known/assetlinks.json` and replace the two
   placeholders with real **SHA-256** fingerprints (colon-separated hex,
   uppercase — the same format the tools print):
   - Debug cert: Gradle `signingReport`, the `SHA-256:` line of the debug
     variant (covers Android-Studio installs).
   - Play App Signing cert: Play Console → Test and release → Setup →
     App signing → *App signing key certificate* → SHA-256 (covers
     Play-installed builds).
2. Deploy the site (the file must return 200 directly on
   `https://asimplewaytopray.com/.well-known/assetlinks.json` — the
   verifier does not follow redirects, which is also why the intent filter
   claims only the apex, never www).
3. Reinstall/update the app; Android verifies on install. Check with:
   `adb shell pm get-app-links com.hallowedgains.aswtp` (want
   `verified`), and force a re-check with
   `adb shell pm verify-app-links --re-verify com.hallowedgains.aswtp`.

Once verified, links from reminder emails / shared prayers open straight
into the app, and launcher shortcuts become possible later.

## Nice-to-haves (any time)

- **App icon / splash screen**: the project currently has Capacitor's
  defaults. Put a 1024×1024 logo + 2732×2732 splash source in
  `mobile/assets/` and run `npx @capacitor/assets generate --android`.
- Play's pre-launch report (automatic on internal testing) exercises the
  app on real devices — read it, it's free QA.

## Ongoing

- Web deploys update the app content immediately; no store release needed.
- A new APK/AAB is only needed when `mobile/` changes: Capacitor/plugin
  upgrades or config changes. After any `mobile/package.json` change run
  `npx cap sync android` and commit the result.
- iOS later reuses this exact project: `npx cap add ios`, plus the items in
  `docs/native-apps.md` step 5 (Sign in with Apple, APNs, Guideline 4.2).
