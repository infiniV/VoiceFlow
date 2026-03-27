#!/bin/bash
# Build Linux release artifacts (tarball + AppImage)
# Run from project root AFTER: pnpm run build
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION=$(node -p "require('$PROJECT_ROOT/package.json').version")
APP_NAME="VoiceFlow"
DIST_DIR="$PROJECT_ROOT/dist"
PYINSTALLER_OUT="$DIST_DIR/$APP_NAME"
OUTPUT_DIR="$DIST_DIR/installer"
ARCH="x86_64"

echo "=== Building Linux release artifacts for $APP_NAME v$VERSION ==="

# Verify PyInstaller output exists
if [ ! -d "$PYINSTALLER_OUT" ]; then
    echo "ERROR: PyInstaller output not found at $PYINSTALLER_OUT"
    echo "Run 'pnpm run build' first."
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# ============================================================================
# 1. Tarball (.tar.gz)
# ============================================================================
echo ""
echo "--- Building tarball ---"

TARBALL_NAME="$APP_NAME-$VERSION-linux-$ARCH"
TARBALL_PATH="$OUTPUT_DIR/$TARBALL_NAME.tar.gz"

# Create a staging directory with a nice top-level folder name
STAGING="$DIST_DIR/$TARBALL_NAME"
rm -rf "$STAGING"
cp -a "$PYINSTALLER_OUT" "$STAGING"

# Ensure the main binary is executable
chmod +x "$STAGING/$APP_NAME"

# Create the tarball
(cd "$DIST_DIR" && tar czf "$OUTPUT_DIR/$TARBALL_NAME.tar.gz" "$TARBALL_NAME")
rm -rf "$STAGING"

TARBALL_SIZE=$(du -h "$TARBALL_PATH" | cut -f1)
echo "Created: $TARBALL_PATH ($TARBALL_SIZE)"

# ============================================================================
# 2. AppImage
# ============================================================================
echo ""
echo "--- Building AppImage ---"

APPIMAGE_NAME="$APP_NAME-$VERSION-$ARCH.AppImage"
APPIMAGE_PATH="$OUTPUT_DIR/$APPIMAGE_NAME"

# Check for appimagetool
APPIMAGETOOL=""
if command -v appimagetool &>/dev/null; then
    APPIMAGETOOL="appimagetool"
elif [ -x "$DIST_DIR/appimagetool" ]; then
    APPIMAGETOOL="$DIST_DIR/appimagetool"
else
    echo "appimagetool not found. Downloading..."
    TOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    curl -fSL "$TOOL_URL" -o "$DIST_DIR/appimagetool"
    chmod +x "$DIST_DIR/appimagetool"
    APPIMAGETOOL="$DIST_DIR/appimagetool"
    echo "Downloaded appimagetool"
fi

# Build AppDir structure
APPDIR="$DIST_DIR/$APP_NAME.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

# Copy PyInstaller output into AppDir root
cp -a "$PYINSTALLER_OUT/." "$APPDIR/"

# Copy AppRun and .desktop
cp "$SCRIPT_DIR/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
cp "$SCRIPT_DIR/VoiceFlow.desktop" "$APPDIR/VoiceFlow.desktop"

# Copy icon (AppImage needs it at root and in hicolor)
cp "$PROJECT_ROOT/src-pyloid/icons/icon.png" "$APPDIR/voiceflow.png"
cp "$PROJECT_ROOT/src-pyloid/icons/icon.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/voiceflow.png"

# Ensure main binary is executable
chmod +x "$APPDIR/$APP_NAME"

# Build the AppImage
ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$APPIMAGE_PATH"
rm -rf "$APPDIR"

APPIMAGE_SIZE=$(du -h "$APPIMAGE_PATH" | cut -f1)
echo "Created: $APPIMAGE_PATH ($APPIMAGE_SIZE)"

# ============================================================================
# Summary
# ============================================================================
echo ""
echo "=== Linux build complete ==="
echo "  Tarball:  $TARBALL_PATH ($TARBALL_SIZE)"
echo "  AppImage: $APPIMAGE_PATH ($APPIMAGE_SIZE)"
echo ""
echo "To test the AppImage:"
echo "  chmod +x $APPIMAGE_PATH && $APPIMAGE_PATH"
