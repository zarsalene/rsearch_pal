# Research Pal for the phone (Android)

The phone app is the web app (`../web`) inside a native shell (Capacitor).
It has no UI code of its own. A change in `web/src/` is also a change in the phone app.

## How it links to the other parts

| To | How |
|---|---|
| `web/` | `webDir` in `capacitor.config.json` is `../web/dist`. `npm run sync` builds the web app, then copies the build into `android/`. |
| `backend/` | HTTP. The address is `VITE_API_URL`. It is fixed when the web app is built. On a phone, `localhost` is the phone itself, so use the Render address (or the IP address of your computer). The backend always allows the origin of the phone app. |

The phone functions (haptics, status bar, back button) are in `web/src/native.js`. They do nothing in a normal browser.

## Commands

Run them in this folder.

```bash
npm install          # one time
npm run sync         # builds ../web and copies web/dist into android/
npm run android      # sync, then opens Android Studio
npm run phone        # phone simulator on your PC (it runs ../web)
npm test             # the phone layout tests (they run in ../web)
npm run icons        # makes the launcher icons from web/public/logo.png (needs Pillow)
```

Build the APK by hand (needs JDK 21 and the Android SDK):

```bash
npm run sync
cd android
./gradlew assembleRelease      # Windows: gradlew.bat assembleRelease
```

GitHub builds the signed APK for you: `.github/workflows/android-apk.yml`.

## Plugin versions

The Capacitor plugins are in `package.json` of both folders:

- `web/package.json` has the JavaScript side (the web code imports them).
- `mobile/package.json` has the native side (Gradle reads them from `mobile/node_modules`).

Keep the same versions in both files.
