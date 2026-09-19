#!/bin/sh
# Build attest-hid and wrap it in a minimal .app bundle. macOS grants Input Monitoring to the
# *responsible application*; a bare executable launched from Terminal would get Terminal's
# permission, so the helper ships as an app with no UI (LSUIElement).
#
#   ./bundle.sh            -> dist/attest-hid.app (ad-hoc signed)
#   open dist/attest-hid.app
#   codesign -dvvv dist/attest-hid.app 2>&1 | grep CDHash    # the value to pin in ATTEST_HID_TRUSTED_CDHASHES
set -e
cd "$(dirname "$0")"
swift build -c release
APP=dist/attest-hid.app
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp .build/release/attest-hid "$APP/Contents/MacOS/attest-hid"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>xyz.attest.hid</string>
  <key>CFBundleName</key><string>attest-hid</string>
  <key>CFBundleExecutable</key><string>attest-hid</string>
  <key>CFBundleVersion</key><string>0.1.0</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHumanReadableCopyright</key><string>HackMIT 2026 — counts physical key-downs; never records which keys.</string>
</dict></plist>
PLIST
# Ad-hoc signature: enough for a stable CDHash and for TCC to recognise the app across launches.
# Production would use a Developer ID + notarization (see docs/L3-hardware-witness.md §6).
codesign --force --sign - --identifier xyz.attest.hid "$APP"
echo "built $APP"
codesign -dvvv "$APP" 2>&1 | grep -E "^CDHash|^Identifier"
