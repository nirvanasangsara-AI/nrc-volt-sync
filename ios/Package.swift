// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "HealthOutboxCore",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "HealthOutboxCore", targets: ["HealthOutboxCore"]),
    ],
    targets: [
        .target(name: "HealthOutboxCore"),
        .testTarget(name: "HealthOutboxCoreTests", dependencies: ["HealthOutboxCore"]),
    ]
)
