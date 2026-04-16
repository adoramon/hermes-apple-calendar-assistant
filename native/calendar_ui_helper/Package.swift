// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "calendar_ui_helper",
    platforms: [
        .macOS(.v12)
    ],
    products: [
        .executable(name: "calendar_ui_helper", targets: ["calendar_ui_helper"])
    ],
    targets: [
        .executableTarget(name: "calendar_ui_helper")
    ]
)
