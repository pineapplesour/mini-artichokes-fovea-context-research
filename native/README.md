# Native Thin Shell

This directory holds the minimum native wrapper source for the shared beta-6 products.

The policy is intentionally narrow:

- Android and iOS use a thin WebView wrapper.
- Android includes a minimal Android Gradle project under `native/android`.
- iOS includes a minimal iOS Swift package under `native/ios`.
- Both wrappers load product routes from `app-shell-manifest.json`.
- The single source of truth is `web/app-shell-manifest.json`.
- Run `tools/sync_native_shell_assets.py` after changing the web manifest.
- Product code must not hardcode product routes. do not hardcode product routes in native source; use `entryRoute` and `chatRoute` from the manifest.
- Web storage remains shared with the PWA contract through the WebView runtime: local chat store, IndexedDB outbox, anonymous session token, job events, job progress, and source-window APIs.

The native build scaffolds are intentionally thin. They exist to keep the app entrypoints, manifest asset, storage policy, and route loading contract in the same repository as the web/PWA shell without adding product-specific native UI.

The small APK size is expected. The Android app is a thin WebView wrapper that uses the device's system WebView and loads the product UI/API from the configured origin. It is not limited to a tiny feature set, but product functionality must come through the shared web/API/engine contract rather than product-specific native screens. If a product needs bundled offline assets later, that must be added deliberately and rechecked against low-bandwidth and app-parity budgets.

## Sync

```bash
python3 tools/sync_native_shell_assets.py
python3 tools/sync_native_shell_assets.py --check
```

## Native Project Entrypoints

- Android Gradle project: `native/android/settings.gradle.kts`
- Android local Gradle runner: `native/android/gradlew`
- Android app module: `native/android/app/build.gradle.kts`
- Android manifest: `native/android/app/src/main/AndroidManifest.xml`
- iOS Swift package: `native/ios/Package.swift`
- iOS app entrypoint: `native/ios/App/NativeShellApp.swift`
- iOS app Info.plist: `native/ios/App/Info.plist`

## Runtime Inputs

- Product key: `islam`, `tcm`, or `simli`.
- Base origin: the deployed same-origin API host for the product.
- Chat mode: opens the manifest `chatRoute` instead of `entryRoute`.

The wrappers must only allow navigation inside the configured origin.

## Build A Product APK

Android debug builds can stamp the product label, default product, and default origin at build time:

```bash
cd native/android
./gradlew :app:assembleDebug --no-daemon \
  -PappLabel='Hikmah AI' \
  -PdefaultProduct=islam \
  -PdefaultBaseOrigin=https://example-product-origin.invalid
```

Inputs:

- `-PappLabel`: Android launcher label.
- `-PdefaultProduct`: product key from `web/app-shell-manifest.json`.
- `-PdefaultBaseOrigin`: HTTPS origin serving the same product API and web routes.

Before building after product route or manifest changes:

```bash
python3 tools/sync_native_shell_assets.py
python3 tools/sync_native_shell_assets.py --check
pytest tests/test_native_shell_parity.py tests/test_native_build_smoke.py -q
python3 tools/verify_app_parity.py --json
```

Expected debug APK path:

```text
native/android/app/build/outputs/apk/debug/app-debug.apk
```

For Windows-facing handoff on this workstation, copy finished APKs to `/mnt/d/downloads/`.

Runtime verification should install and launch the APK on a device or emulator when available:

```bash
python3 tools/verify_android_runtime_smoke.py \
  --apk native/android/app/build/outputs/apk/debug/app-debug.apk \
  --output runs/android_runtime_<product>_<date>.json
```

For full user-path proof, run the WebView submit verifier against the installed app when an Android device or emulator is available:

```bash
python3 tools/verify_android_webview_submit_smoke.py \
  --product islam \
  --output runs/android_webview_submit_islam_<date>.json
```
