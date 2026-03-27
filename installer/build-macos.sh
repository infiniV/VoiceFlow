#!/bin/bash
# Build macOS release artifact (.dmg)
# Run from project root AFTER: pnpm run build
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION=$(node -p "require('$PROJECT_ROOT/package.json').version")
APP_NAME="VoiceFlow"
DIST_DIR="$PROJECT_ROOT/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
OUTPUT_DIR="$DIST_DIR/installer"

echo "=== Building macOS release artifact for $APP_NAME v$VERSION ==="

# Verify PyInstaller .app bundle exists
if [ ! -d "$APP_BUNDLE" ]; then
    echo "ERROR: App bundle not found at $APP_BUNDLE"
    echo "Run 'pnpm run build' first."
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

DMG_NAME="$APP_NAME-$VERSION.dmg"
DMG_PATH="$OUTPUT_DIR/$DMG_NAME"
STAGING="$DIST_DIR/dmg-staging"

# Clean up any previous staging
rm -rf "$STAGING" "$DMG_PATH"

# Create staging directory with Applications symlink
mkdir -p "$STAGING"
cp -a "$APP_BUNDLE" "$STAGING/"
ln -s /Applications "$STAGING/Applications"

# Create the DMG
echo "Creating DMG..."
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$STAGING" \
    -ov \
    -format UDZO \
    -imagekey zlib-level=9 \
    "$DMG_PATH"

rm -rf "$STAGING"

DMG_SIZE=$(du -h "$DMG_PATH" | cut -f1)
echo ""
echo "=== macOS build complete ==="
echo "  DMG: $DMG_PATH ($DMG_SIZE)"
