// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "BunjumBeta6Native",
    platforms: [.iOS(.v15)],
    products: [
        .executable(name: "BunjumBeta6Native", targets: ["BunjumBeta6Native"])
    ],
    targets: [
        .executableTarget(
            name: "BunjumBeta6Native",
            path: ".",
            sources: [
                "App/NativeShellApp.swift",
                "Sources/NativeShellViewController.swift"
            ],
            resources: [.process("Resources")],
            linkerSettings: [
                .linkedFramework("UIKit"),
                .linkedFramework("WebKit")
            ]
        )
    ]
)
