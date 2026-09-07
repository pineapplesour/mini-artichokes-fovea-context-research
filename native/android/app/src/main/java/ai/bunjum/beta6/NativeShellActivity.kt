package ai.bunjum.beta6

import android.annotation.SuppressLint
import android.app.Activity
import android.content.pm.ApplicationInfo
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.view.WindowManager
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import org.json.JSONObject
import java.io.FileNotFoundException
import java.net.URLConnection
import java.util.Locale

class NativeShellActivity : Activity() {
    private lateinit var webView: WebView
    private lateinit var allowedOrigin: Uri

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val manifest = readAppShellManifest()
        val productKey = intent.getStringExtra(EXTRA_PRODUCT) ?: DEFAULT_PRODUCT
        val openChat = intent.getBooleanExtra(EXTRA_CHAT, false)
        val route = resolveRoute(manifest, productKey, openChat)

        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
        allowedOrigin = Uri.parse(intent.getStringExtra(EXTRA_BASE_ORIGIN) ?: DEFAULT_BASE_ORIGIN)
        if ((applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
            WebView.setWebContentsDebuggingEnabled(true)
        }
        webView = WebView(this)
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            cacheMode = if (BuildConfig.EMBED_FRONTEND) WebSettings.LOAD_NO_CACHE else WebSettings.LOAD_DEFAULT
            loadsImagesAutomatically = true
            mediaPlaybackRequiresUserGesture = true
        }
        if (BuildConfig.EMBED_FRONTEND) {
            webView.clearCache(true)
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                return !isAllowed(request.url)
            }

            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                if (!isEmbeddedFrontendRequest(request)) return null
                return embeddedAssetResponse(request.url)
            }
        }
        webView.setBackgroundColor(SYSTEM_BAR_COLOR)
        val container = FrameLayout(this)
        container.setBackgroundColor(SYSTEM_BAR_COLOR)
        container.addView(
            webView,
            FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT),
        )
        container.setOnApplyWindowInsetsListener { view, insets ->
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                val bars = insets.getInsets(WindowInsets.Type.systemBars())
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            } else {
                @Suppress("DEPRECATION")
                view.setPadding(
                    insets.systemWindowInsetLeft,
                    insets.systemWindowInsetTop,
                    insets.systemWindowInsetRight,
                    insets.systemWindowInsetBottom,
                )
            }
            insets
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            window.statusBarColor = SYSTEM_BAR_COLOR
            window.navigationBarColor = SYSTEM_BAR_COLOR
        }
        setContentView(container)
        container.requestApplyInsets()
        webView.loadUrl(allowedOrigin.buildUpon().encodedPath(route).build().toString())
    }

    private fun readAppShellManifest(): JSONObject {
        val json = assets.open("app-shell-manifest.json").bufferedReader(Charsets.UTF_8).use { it.readText() }
        return JSONObject(json)
    }

    private fun resolveRoute(manifest: JSONObject, productKey: String, openChat: Boolean): String {
        val products = manifest.getJSONObject("products")
        if (products.has(productKey)) {
            val native = products.getJSONObject(productKey).getJSONObject("native")
            // Keep these reads explicit so native storage policy cannot drift silently.
            native.getString("offlineStore")
            native.getString("sessionTokenStore")
            native.getString("accountSubjectStore")
            return native.getString(if (openChat) "chatRoute" else "entryRoute")
        }

        val fallbackRoute = if (openChat) DEFAULT_CHAT_ROUTE else DEFAULT_ENTRY_ROUTE
        require(fallbackRoute.isNotBlank()) {
            "Missing product in app-shell-manifest.json and no build-time route was provided: $productKey"
        }
        return fallbackRoute
    }

    private fun isAllowed(uri: Uri): Boolean {
        return uri.scheme == allowedOrigin.scheme && uri.host == allowedOrigin.host && uri.port == allowedOrigin.port
    }

    private fun isEmbeddedFrontendRequest(request: WebResourceRequest): Boolean {
        if (!BuildConfig.EMBED_FRONTEND) return false
        if (request.method.uppercase(Locale.ROOT) != "GET") return false
        if (!isAllowed(request.url)) return false
        val path = request.url.path ?: "/"
        if (path.startsWith("/api/")) return false
        return true
    }

    private fun embeddedAssetResponse(uri: Uri): WebResourceResponse? {
        val assetPath = embeddedAssetPath(uri) ?: return null
        return try {
            WebResourceResponse(
                mimeTypeFor(assetPath),
                charsetFor(assetPath),
                assets.open(assetPath),
            ).apply {
                responseHeaders = mapOf("Cache-Control" to "no-store")
            }
        } catch (_: FileNotFoundException) {
            null
        }
    }

    private fun embeddedAssetPath(uri: Uri): String? {
        val raw = (uri.path ?: "/").removePrefix("/")
        val relative = when {
            raw.isBlank() -> "index.html"
            raw.startsWith("static/") -> raw.removePrefix("static/")
            raw.endsWith("/") -> raw + "index.html"
            else -> raw
        }
        if (relative.split('/').any { it == ".." || it.isBlank() }) return null
        return "${BuildConfig.EMBEDDED_WEB_ROOT}/$relative"
    }

    private fun mimeTypeFor(assetPath: String): String {
        return URLConnection.guessContentTypeFromName(assetPath) ?: when {
            assetPath.endsWith(".js") -> "application/javascript"
            assetPath.endsWith(".css") -> "text/css"
            assetPath.endsWith(".html") -> "text/html"
            assetPath.endsWith(".json") || assetPath.endsWith(".webmanifest") -> "application/json"
            else -> "application/octet-stream"
        }
    }

    private fun charsetFor(assetPath: String): String? {
        return if (
            assetPath.endsWith(".html") ||
            assetPath.endsWith(".js") ||
            assetPath.endsWith(".css") ||
            assetPath.endsWith(".json") ||
            assetPath.endsWith(".webmanifest")
        ) {
            "UTF-8"
        } else {
            null
        }
    }

    companion object {
        const val EXTRA_PRODUCT = "ai.bunjum.beta6.PRODUCT"
        const val EXTRA_CHAT = "ai.bunjum.beta6.CHAT"
        const val EXTRA_BASE_ORIGIN = "ai.bunjum.beta6.BASE_ORIGIN"
        private const val DEFAULT_PRODUCT = BuildConfig.DEFAULT_PRODUCT
        private const val DEFAULT_BASE_ORIGIN = BuildConfig.DEFAULT_BASE_ORIGIN
        private const val DEFAULT_ENTRY_ROUTE = BuildConfig.DEFAULT_ENTRY_ROUTE
        private const val DEFAULT_CHAT_ROUTE = BuildConfig.DEFAULT_CHAT_ROUTE
        private val SYSTEM_BAR_COLOR = Color.rgb(30, 33, 28)
    }
}
