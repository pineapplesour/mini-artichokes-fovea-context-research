import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_MANIFEST = ROOT / "web" / "app-shell-manifest.json"
SYNC_SCRIPT = ROOT / "tools" / "sync_native_shell_assets.py"
ANDROID_ACTIVITY = ROOT / "native" / "android" / "app" / "src" / "main" / "java" / "ai" / "bunjum" / "beta6" / "NativeShellActivity.kt"
ANDROID_ASSET = ROOT / "native" / "android" / "app" / "src" / "main" / "assets" / "app-shell-manifest.json"
IOS_CONTROLLER = ROOT / "native" / "ios" / "Sources" / "NativeShellViewController.swift"
IOS_ASSET = ROOT / "native" / "ios" / "Resources" / "app-shell-manifest.json"
README = ROOT / "native" / "README.md"
ANDROID_SETTINGS = ROOT / "native" / "android" / "settings.gradle.kts"
ANDROID_ROOT_BUILD = ROOT / "native" / "android" / "build.gradle.kts"
ANDROID_APP_BUILD = ROOT / "native" / "android" / "app" / "build.gradle.kts"
ANDROID_GRADLEW = ROOT / "native" / "android" / "gradlew"
ANDROID_MANIFEST = ROOT / "native" / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
ANDROID_STYLES = ROOT / "native" / "android" / "app" / "src" / "main" / "res" / "values" / "styles.xml"
IOS_PACKAGE = ROOT / "native" / "ios" / "Package.swift"
IOS_APP = ROOT / "native" / "ios" / "App" / "NativeShellApp.swift"
IOS_INFO = ROOT / "native" / "ios" / "App" / "Info.plist"


def _manifest(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_native_shell_assets_are_synced_from_single_web_manifest():
    assert WEB_MANIFEST.exists()
    assert SYNC_SCRIPT.exists()
    assert ANDROID_ASSET.exists()
    assert IOS_ASSET.exists()

    web_manifest = _manifest(WEB_MANIFEST)
    assert _manifest(ANDROID_ASSET) == web_manifest
    assert _manifest(IOS_ASSET) == web_manifest

    script = SYNC_SCRIPT.read_text(encoding="utf-8")
    assert "web/app-shell-manifest.json" in script
    assert "native/android/app/src/main/assets/app-shell-manifest.json" in script
    assert "native/ios/Resources/app-shell-manifest.json" in script


def test_android_native_shell_consumes_manifest_routes_and_shared_web_storage():
    text = ANDROID_ACTIVITY.read_text(encoding="utf-8")

    for token in (
        "ApplicationInfo.FLAG_DEBUGGABLE",
        "WebView.setWebContentsDebuggingEnabled(true)",
        "app-shell-manifest.json",
        "entryRoute",
        "chatRoute",
        "offlineStore",
        "sessionTokenStore",
        "accountSubjectStore",
        "domStorageEnabled = true",
        "databaseEnabled = true",
        "javaScriptEnabled = true",
        "shouldOverrideUrlLoading",
        "allowedOrigin",
        "setOnApplyWindowInsetsListener",
        "WindowInsets.Type.systemBars()",
        "setPadding",
        "shouldInterceptRequest",
        "EMBED_FRONTEND",
        "WebResourceResponse",
        "isEmbeddedFrontendRequest",
        "embeddedAssetResponse",
        "raw.startsWith(\"static/\")",
        "raw.removePrefix(\"static/\")",
        "path.startsWith(\"/api/\")",
        "assets.open",
        "SYSTEM_BAR_COLOR",
        "window.statusBarColor = SYSTEM_BAR_COLOR",
        "window.navigationBarColor = SYSTEM_BAR_COLOR",
        "webView.setBackgroundColor(SYSTEM_BAR_COLOR)",
    ):
        assert token in text

    assert "SYSTEM_UI_FLAG_LIGHT_STATUS_BAR" not in text

    assert '"/islam.html"' not in text
    assert '"/tcm.html"' not in text
    assert '"/simli.html"' not in text


def test_ios_native_shell_consumes_manifest_routes_and_shared_web_storage():
    text = IOS_CONTROLLER.read_text(encoding="utf-8")

    for token in (
        "app-shell-manifest",
        "WKWebView",
        "entryRoute",
        "chatRoute",
        "offlineStore",
        "sessionTokenStore",
        "accountSubjectStore",
        "websiteDataStore",
        "allowedOrigin",
        "decidePolicyFor",
    ):
        assert token in text

    assert '"/islam.html"' not in text
    assert '"/tcm.html"' not in text
    assert '"/simli.html"' not in text


def test_native_shell_readme_marks_scope_and_no_route_drift_policy():
    text = README.read_text(encoding="utf-8")

    assert "thin WebView" in text
    assert "web/app-shell-manifest.json" in text
    assert "tools/sync_native_shell_assets.py" in text
    assert "Android Gradle project" in text
    assert "iOS Swift package" in text
    assert "do not hardcode product routes" in text


def test_android_native_shell_has_gradle_project_scaffold():
    for path in (ANDROID_SETTINGS, ANDROID_ROOT_BUILD, ANDROID_APP_BUILD, ANDROID_MANIFEST, ANDROID_STYLES):
        assert path.exists(), path

    settings = ANDROID_SETTINGS.read_text(encoding="utf-8")
    root_build = ANDROID_ROOT_BUILD.read_text(encoding="utf-8")
    app_build = ANDROID_APP_BUILD.read_text(encoding="utf-8")
    manifest = ANDROID_MANIFEST.read_text(encoding="utf-8")
    styles = ANDROID_STYLES.read_text(encoding="utf-8")

    assert 'include(":app")' in settings
    assert 'id("com.android.application")' in root_build
    assert 'id("org.jetbrains.kotlin.android")' in root_build
    assert 'namespace = "ai.bunjum.beta6"' in app_build
    assert 'minSdk = 23' in app_build
    assert 'targetSdk = 35' in app_build
    assert "sourceCompatibility = JavaVersion.VERSION_17" in app_build
    assert "targetCompatibility = JavaVersion.VERSION_17" in app_build
    assert "jvmToolchain(17)" in app_build
    assert 'NativeShellActivity' in manifest
    assert 'android.permission.INTERNET' in manifest
    assert 'android:usesCleartextTraffic="false"' in manifest
    assert 'android:exported="true"' in manifest
    assert 'android:theme="@style/NativeShellTheme"' in manifest
    assert 'android:icon="@drawable/ic_launcher"' in manifest
    assert 'android:roundIcon="@drawable/ic_launcher_round"' in manifest
    assert "Theme.Material.NoActionBar" in styles
    assert "android:windowNoTitle" in styles
    assert "android:windowActionBar" in styles
    assert "android:windowBackground" in styles
    assert "android:statusBarColor" in styles
    assert "android:navigationBarColor" in styles
    assert "android:windowLightStatusBar" in styles
    assert "android:windowLightNavigationBar" in styles
    assert '"/islam.html"' not in app_build + manifest
    assert '"/tcm.html"' not in app_build + manifest
    assert '"/simli.html"' not in app_build + manifest


def test_android_native_shell_resizes_for_keyboard_without_white_system_chrome():
    manifest = ANDROID_MANIFEST.read_text(encoding="utf-8")
    styles = ANDROID_STYLES.read_text(encoding="utf-8")
    activity = ANDROID_ACTIVITY.read_text(encoding="utf-8")

    assert 'android:windowSoftInputMode="adjustResize"' in manifest
    assert "WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE" in activity
    assert "window.setSoftInputMode" in activity
    assert "setBackgroundColor(SYSTEM_BAR_COLOR)" in activity
    assert "window.statusBarColor = SYSTEM_BAR_COLOR" in activity
    assert "window.navigationBarColor = SYSTEM_BAR_COLOR" in activity
    assert "#1E211C" in styles
    assert "android:windowLightStatusBar\">false" in styles
    assert "android:windowLightNavigationBar\">false" in styles


def test_android_native_shell_can_stamp_product_label_and_default_origin_at_build_time():
    app_build = ANDROID_APP_BUILD.read_text(encoding="utf-8")
    manifest = ANDROID_MANIFEST.read_text(encoding="utf-8")
    activity = ANDROID_ACTIVITY.read_text(encoding="utf-8")

    assert 'manifestPlaceholders["appLabel"]' in app_build
    assert "project.findProperty(name)" in app_build
    assert 'applicationId = stringProperty("applicationId"' in app_build
    assert 'stringProperty("appLabel"' in app_build
    assert 'stringProperty("defaultProduct"' in app_build
    assert 'stringProperty("defaultBaseOrigin"' in app_build
    assert 'stringProperty("defaultEntryRoute"' in app_build
    assert 'stringProperty("defaultChatRoute"' in app_build
    assert 'buildConfigField("String", "DEFAULT_PRODUCT"' in app_build
    assert 'buildConfigField("String", "DEFAULT_BASE_ORIGIN"' in app_build
    assert 'buildConfigField("String", "DEFAULT_ENTRY_ROUTE"' in app_build
    assert 'buildConfigField("String", "DEFAULT_CHAT_ROUTE"' in app_build
    assert 'buildConfigField("Boolean", "EMBED_FRONTEND"' in app_build
    assert 'buildConfigField("String", "EMBEDDED_WEB_ROOT"' in app_build
    assert 'booleanProperty("embedFrontend"' in app_build
    assert 'stringProperty("embeddedWebRoot"' in app_build
    assert "syncEmbeddedWebAssets" in app_build
    assert "generateLauncherIconResources" in app_build
    assert "launcherIconBg" in app_build
    assert "launcherIconAccent" in app_build
    assert "embeddedFrontendDir" in app_build
    assert "generatedLauncherIconResDir" in app_build
    assert "buildConfig = true" in app_build
    assert 'android:label="${appLabel}"' in manifest
    assert 'android:name="ai.bunjum.beta6.NativeShellActivity"' in manifest
    assert "BuildConfig.DEFAULT_PRODUCT" in activity
    assert "BuildConfig.DEFAULT_BASE_ORIGIN" in activity
    assert "BuildConfig.DEFAULT_ENTRY_ROUTE" in activity
    assert "BuildConfig.DEFAULT_CHAT_ROUTE" in activity
    assert "BuildConfig.EMBED_FRONTEND" in activity
    assert "BuildConfig.EMBEDDED_WEB_ROOT" in activity
    assert "WebSettings.LOAD_NO_CACHE" in activity
    assert "webView.clearCache(true)" in activity
    assert "products.has(productKey)" in activity
    assert "no build-time route was provided" in activity


def test_android_native_shell_has_repo_local_gradle_runner():
    assert ANDROID_GRADLEW.exists()
    assert os.access(ANDROID_GRADLEW, os.X_OK)
    text = ANDROID_GRADLEW.read_text(encoding="utf-8")
    assert "gradle-8.10.2-bin.zip" in text
    assert "chmod" in text
    assert "GRADLE_BIN" in text
    assert ":app:assembleDebug" not in text


def test_ios_native_shell_has_swift_package_app_scaffold():
    for path in (IOS_PACKAGE, IOS_APP, IOS_INFO):
        assert path.exists(), path

    package = IOS_PACKAGE.read_text(encoding="utf-8")
    app = IOS_APP.read_text(encoding="utf-8")
    info = IOS_INFO.read_text(encoding="utf-8")

    assert 'platforms: [.iOS(.v15)]' in package
    assert 'executableTarget' in package
    assert 'resources: [.process("Resources")]' in package
    assert "NativeShellViewController" in app
    assert "UIApplicationSceneManifest" in info
    assert "NSAppTransportSecurity" in info
    assert "NSAllowsArbitraryLoads" not in info
    assert '"/islam.html"' not in package + app + info
    assert '"/tcm.html"' not in package + app + info
    assert '"/simli.html"' not in package + app + info


def test_app_parity_verifier_checks_native_sources():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verify_app_parity.py"), "--json"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    report = json.loads(completed.stdout)

    assert report["passes"] is True
    assert report["nativeSource"]["androidSourcePass"] is True
    assert report["nativeSource"]["iosSourcePass"] is True
    assert report["nativeSource"]["androidProjectPass"] is True
    assert report["nativeSource"]["androidGradleRunnerPass"] is True
    assert report["nativeSource"]["iosProjectPass"] is True
    assert report["nativeSource"]["assetsSynced"] is True
