// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "attest-hid",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "attest-hid",
            path: "Sources/attest-hid",
            linkerSettings: [
                .linkedFramework("IOKit"),
                .linkedFramework("Security"),
                .linkedFramework("Network"),
                .linkedFramework("CryptoKit"),
            ]
        ),
    ],
    swiftLanguageVersions: [.v5]
)
