plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

fun stringProperty(name: String, defaultValue: String): String =
    (project.findProperty(name) as String?)?.takeIf { it.isNotBlank() } ?: defaultValue

fun booleanProperty(name: String, defaultValue: Boolean): Boolean =
    (project.findProperty(name) as String?)?.takeIf { it.isNotBlank() }?.toBooleanStrictOrNull() ?: defaultValue

fun buildConfigString(value: String): String = "\"${value.replace("\\", "\\\\").replace("\"", "\\\"")}\""

val embeddedWebRoot = stringProperty("embeddedWebRoot", "embedded-web")
val embeddedFrontendDir = stringProperty("embeddedFrontendDir", "")
val generatedEmbeddedAssetsDir = layout.buildDirectory.dir("generated/embeddedWebAssets")
val launcherIconBg = stringProperty("launcherIconBg", "#1E211C")
val launcherIconAccent = stringProperty("launcherIconAccent", "#C75B3A")
val launcherIconKind = stringProperty("launcherIconKind", "compass")
val launcherIconPng = stringProperty("launcherIconPng", "")
val launcherIconRoundPng = stringProperty("launcherIconRoundPng", "")
val generatedLauncherIconResDir = layout.buildDirectory.dir("generated/launcherIconRes")

android {
    namespace = "ai.bunjum.beta6"
    compileSdk = 35

    defaultConfig {
        applicationId = stringProperty("applicationId", "ai.bunjum.beta6")
        minSdk = 23
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"

        manifestPlaceholders["appLabel"] = stringProperty("appLabel", "Bunjum Beta6")
        buildConfigField("String", "DEFAULT_PRODUCT", buildConfigString(stringProperty("defaultProduct", "islam")))
        buildConfigField("String", "DEFAULT_BASE_ORIGIN", buildConfigString(stringProperty("defaultBaseOrigin", "https://example.invalid")))
        buildConfigField("String", "DEFAULT_ENTRY_ROUTE", buildConfigString(stringProperty("defaultEntryRoute", "")))
        buildConfigField("String", "DEFAULT_CHAT_ROUTE", buildConfigString(stringProperty("defaultChatRoute", "")))
        buildConfigField("Boolean", "EMBED_FRONTEND", booleanProperty("embedFrontend", false).toString())
        buildConfigField("String", "EMBEDDED_WEB_ROOT", buildConfigString(embeddedWebRoot))
    }

    sourceSets["main"].assets.srcDir(generatedEmbeddedAssetsDir)
    sourceSets["main"].res.srcDir(generatedLauncherIconResDir)

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        buildConfig = true
    }
}

val syncEmbeddedWebAssets by tasks.registering(Copy::class) {
    val sourceDir = embeddedFrontendDir
    from(sourceDir)
    into(generatedEmbeddedAssetsDir.map { it.dir(embeddedWebRoot) })
    onlyIf { sourceDir.isNotBlank() && file(sourceDir).exists() }
}

fun launcherIconPaths(bg: String, accent: String, kind: String): String {
    return when (kind.lowercase()) {
        "law" -> """
            <path android:fillColor="$accent" android:pathData="M54,54m-36,0a36,36 0,1 0,72 0a36,36 0,1 0,-72 0"/>
            <path android:fillColor="$bg" android:pathData="M52,28h4v46h-4z"/>
            <path android:fillColor="$bg" android:pathData="M30,38h48v5h-48z"/>
            <path android:fillColor="$bg" android:pathData="M36,44l-12,24h24z"/>
            <path android:fillColor="$bg" android:pathData="M72,44l-12,24h24z"/>
            <path android:fillColor="$bg" android:pathData="M38,76h32v5h-32z"/>
        """.trimIndent()
        "heart" -> """
            <path android:fillColor="$accent" android:pathData="M54,84c-4,-5 -28,-21 -28,-39c0,-11 8,-19 19,-19c5,0 8,2 11,6c3,-4 7,-6 12,-6c11,0 19,8 19,19c0,18 -25,34 -33,39z"/>
            <path android:fillColor="#FFFFFF" android:fillAlpha="0.72" android:pathData="M39,36c-4,2 -7,6 -7,11h5c0,-3 2,-5 5,-7z"/>
        """.trimIndent()
        else -> """
            <path android:fillColor="$accent" android:pathData="M54,54m-36,0a36,36 0,1 0,72 0a36,36 0,1 0,-72 0"/>
            <path android:fillColor="$bg" android:pathData="M54,30m-24,0a24,24 0,1 0,48 0a24,24 0,1 0,-48 0"/>
            <path android:fillColor="#E6E1D8" android:pathData="M52,24h4v60h-4z"/>
            <path android:fillColor="#E6E1D8" android:pathData="M24,52h60v4h-60z"/>
        """.trimIndent()
    }
}

fun launcherIconVector(bg: String, accent: String, kind: String, round: Boolean): String {
    val bgPath = if (round) {
        "M54,0m-54,0a54,54 0,1 0,108 0a54,54 0,1 0,-108 0"
    } else {
        "M0,0h108v108h-108z"
    }
    val paths = launcherIconPaths(bg, accent, kind)
    return """
        <vector xmlns:android="http://schemas.android.com/apk/res/android"
            android:width="108dp"
            android:height="108dp"
            android:viewportWidth="108"
            android:viewportHeight="108">
            <path android:fillColor="$bg" android:pathData="$bgPath"/>
            $paths
        </vector>
    """.trimIndent()
}

val generateLauncherIconResources by tasks.registering {
    inputs.property("launcherIconBg", launcherIconBg)
    inputs.property("launcherIconAccent", launcherIconAccent)
    inputs.property("launcherIconKind", launcherIconKind)
    inputs.property("launcherIconPng", launcherIconPng)
    inputs.property("launcherIconRoundPng", launcherIconRoundPng)
    outputs.dir(generatedLauncherIconResDir)
    doLast {
        val drawableDir = generatedLauncherIconResDir.get().dir("drawable").asFile
        drawableDir.mkdirs()
        drawableDir.listFiles()?.forEach { it.delete() }
        if (launcherIconPng.isNotBlank()) {
            copy {
                from(file(launcherIconPng))
                into(drawableDir)
                rename { "ic_launcher.png" }
            }
            copy {
                from(file(launcherIconRoundPng.ifBlank { launcherIconPng }))
                into(drawableDir)
                rename { "ic_launcher_round.png" }
            }
            return@doLast
        }
        drawableDir.resolve("ic_launcher.xml").writeText(
            launcherIconVector(launcherIconBg, launcherIconAccent, launcherIconKind, false),
            Charsets.UTF_8,
        )
        drawableDir.resolve("ic_launcher_round.xml").writeText(
            launcherIconVector(launcherIconBg, launcherIconAccent, launcherIconKind, true),
            Charsets.UTF_8,
        )
    }
}

tasks.named("preBuild").configure {
    dependsOn(syncEmbeddedWebAssets)
    dependsOn(generateLauncherIconResources)
}

kotlin {
    jvmToolchain(17)
}
