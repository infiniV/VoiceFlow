# VoiceFlow Release Guide

## Prerequisites

All platforms need:
- Node.js + pnpm
- Python + uv (with `.venv` set up via `pnpm run setup`)

### Windows
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) installed (for installer)

### Linux
- `appimagetool` (auto-downloaded by build script if not on PATH)

### macOS
- `hdiutil` (ships with macOS)

## Version Bump

1. Update version in `package.json`
2. Update version in `installer/voiceflow.iss` (`MyAppVersion`)
3. Commit: `git commit -am "chore: bump version to X.Y.Z"`
4. Tag: `git tag vX.Y.Z`

## Building

### Windows

```bash
pnpm run build:installer
```

Output: `dist/installer/VoiceFlowSetup-{version}.exe`

### Linux

```bash
pnpm run build:installer:linux
```

Output:
- `dist/installer/VoiceFlow-{version}-linux-x86_64.tar.gz`
- `dist/installer/VoiceFlow-{version}-x86_64.AppImage`

### macOS

```bash
pnpm run build:installer:macos
```

Output: `dist/installer/VoiceFlow-{version}.dmg`

## Creating a GitHub Release

After building on each platform:

```bash
# Push the tag
git push origin vX.Y.Z

# Create the release with all artifacts
gh release create vX.Y.Z \
  dist/installer/VoiceFlowSetup-X.Y.Z.exe \
  dist/installer/VoiceFlow-X.Y.Z-linux-x86_64.tar.gz \
  dist/installer/VoiceFlow-X.Y.Z-x86_64.AppImage \
  dist/installer/VoiceFlow-X.Y.Z.dmg \
  --title "VoiceFlow vX.Y.Z" \
  --notes "Release notes here"
```

Since builds are platform-native (PyInstaller doesn't cross-compile), you need to build on each OS. Upload assets incrementally:

```bash
# From Windows machine:
gh release upload vX.Y.Z dist/installer/VoiceFlowSetup-X.Y.Z.exe

# From Linux machine:
gh release upload vX.Y.Z dist/installer/VoiceFlow-X.Y.Z-linux-x86_64.tar.gz
gh release upload vX.Y.Z dist/installer/VoiceFlow-X.Y.Z-x86_64.AppImage

# From macOS machine:
gh release upload vX.Y.Z dist/installer/VoiceFlow-X.Y.Z.dmg
```

## Testing Before Release

- **Windows**: Run the installer, verify tray icon + hotkey + transcription
- **Linux**: Run AppImage (`chmod +x *.AppImage && ./VoiceFlow*.AppImage`), test hotkey via evdev
- **macOS**: Mount DMG, drag to Applications, launch and test
