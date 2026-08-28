#!/usr/bin/env bash
#
# build-preview.sh — Build a local preview version of Thaw for macOS 27
#
# This script replicates the GitHub Actions "Build DMG" workflow for local use.
# It builds an unsigned (ad-hoc) copy of Thaw suitable for testing on macOS 27.
#
# Prerequisites:
#   - Xcode 27+ installed (xcodebuild must be available)
#   - macOS 27 (Golden Gate) or later
#
# Usage:
#   ./build-preview.sh              # Build + install to /Applications
#   ./build-preview.sh --dmg         # Also create a DMG
#   ./build-preview.sh --debug       # Build Debug config (like thaw-devrun.sh)
#   ./build-preview.sh --run         # Launch after building
#   ./build-preview.sh --help        # Show help
#
set -euo pipefail
cd "$(dirname "$0")/.."

SCHEME="Thaw"
PROJECT="Thaw.xcodeproj"
WORKSPACE="ThawDev.xcworkspace"
CONFIG="Release"
DEST="/Applications/Thaw Preview.app"
BUNDLE_ID="com.stonerl.Thaw"
BUILD_DMG=0
RUN_AFTER=0
DERIVED_DATA="Build/"
export MENU_BAR_MODEL_PATH="$PWD/MenuBarModel"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dmg)      BUILD_DMG=1; shift ;;
        --debug)    CONFIG="Debug"; DEST="/Applications/Thaw Debug.app"; BUNDLE_ID="com.stonerl.Thaw.debug"; shift ;;
        --run)      RUN_AFTER=1; shift ;;
        -h|--help)
            sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
done

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m✗\033[0m %s\n' "$*" >&2; }

# ── Step 1: Check for Xcode ──────────────────────────────────────────────

say "Checking for Xcode…"

if ! xcrun --find xcodebuild &>/dev/null; then
    err "Xcode is not installed. xcodebuild is required to build Thaw."
    echo ""
    echo "To install Xcode:"
    echo "  1. Download Xcode 27 beta from https://developer.apple.com/download/"
    echo "  2. Move Xcode.app to /Applications/"
    echo "  3. Run: sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
    echo "  4. Run: sudo xcodebuild -runFirstLaunch"
    echo ""
    echo "Then re-run this script."
    exit 1
fi

XCODE_VERSION=$(xcodebuild -version | head -1)
say "Found: $XCODE_VERSION"

# ── Step 2: Resolve Swift Package dependencies ──────────────────────────

say "Resolving Swift package dependencies…"
xcodebuild -project "$PROJECT" -scheme "$SCHEME" \
    -resolvePackageDependencies \
    -onlyUsePackageVersionsFromResolvedFile 2>&1 || {
    err "Failed to resolve package dependencies."
    err "Check your network connection and Package.resolved file."
    exit 1
}

# ── Step 3: Build the app (unsigned) ────────────────────────────────────

say "Building Thaw (${CONFIG})…"

# Use CODE_SIGNING_ALLOWED=NO for unsigned local builds (per AGENTS.md)
xcodebuild build \
    -project "$PROJECT" \
    -scheme "$SCHEME" \
    -configuration "$CONFIG" \
    -destination 'platform=macOS' \
    -derivedDataPath "$DERIVED_DATA" \
    -onlyUsePackageVersionsFromResolvedFile \
    CODE_SIGN_IDENTITY="" \
    CODE_SIGNING_REQUIRED=NO \
    CODE_SIGNING_ALLOWED=NO \
    2>&1 || {
    err "Build failed."
    exit 1
}

# ── Step 4: Locate the built .app ──────────────────────────────────────

say "Locating build product…"

PRODUCTS_DIR=$(xcodebuild \
    -project "$PROJECT" \
    -scheme "$SCHEME" \
    -configuration "$CONFIG" \
    -derivedDataPath "$DERIVED_DATA" \
    -showBuildSettings 2>/dev/null \
    | awk -F' = ' '/ BUILT_PRODUCTS_DIR /{print $2; exit}')

APP="${PRODUCTS_DIR}/Thaw.app"

if [[ ! -d "$APP" ]]; then
    err "Build product not found at: $APP"
    err "Check the build output above for errors."
    exit 1
fi

say "Built: $APP"

# ── Step 5: Ad-hoc sign the app (so it can run locally) ─────────────────

say "Ad-hoc signing (for local execution)…"
codesign --force --deep --sign - "$APP" 2>&1 || {
    err "Ad-hoc signing failed. The app may not run without this."
    echo "You can try: codesign --force --deep --sign - \"$APP\""
}

# ── Step 6: Quit running instances and install ──────────────────────────

quit_thaw() {
    pgrep -f "$DEST/" >/dev/null 2>&1 || return 0
    say "Quitting running Thaw…"
    ( osascript -e "tell application id \"$BUNDLE_ID\" to quit" >/dev/null 2>&1 ) &
    for _ in {1..8}; do
        pgrep -f "$DEST/" >/dev/null 2>&1 || return 0
        sleep 0.5
    done
    say "Force-killing leftover processes…"
    pkill -9 -f "$DEST/" 2>/dev/null || true
    sleep 1
}

quit_thaw

if [[ -e "$DEST" ]]; then
    say "Removing existing ${DEST}…"
    rm -rf "$DEST"
fi

say "Installing to ${DEST}…"
cp -R "$APP" "$DEST"

# ── Step 7: Optionally create a DMG ─────────────────────────────────────

if [[ "$BUILD_DMG" -eq 1 ]]; then
    say "Creating DMG…"

    if ! command -v create-dmg &>/dev/null; then
        say "Installing create-dmg via Homebrew…"
        brew install create-dmg 2>&1 || {
            err "Failed to install create-dmg. Skipping DMG creation."
        }
    fi

    if command -v create-dmg &>/dev/null; then
        STAGING="$TMPDIR/thaw-dmg-staging"
        rm -rf "$STAGING"
        mkdir -p "$STAGING"
        cp -R "$DEST" "$STAGING/Thaw.app"
        ln -s /Applications "$STAGING/Applications"

        DMG_NAME="Thaw-preview.dmg"
        DMG_PATH="$(pwd)/${DMG_NAME}"

        create-dmg \
            --volname "Thaw" \
            --window-size 582 300 \
            --icon-size 100 \
            --hide-extension "Thaw.app" \
            --icon "Thaw.app" 150 150 \
            --icon "Applications" 436 150 \
            "$DMG_PATH" \
            "$STAGING" 2>&1 || {
            err "DMG creation failed."
        }

        rm -rf "$STAGING"
        say "DMG created: $DMG_PATH"
    fi
fi

# ── Step 8: Optionally launch ───────────────────────────────────────────

if [[ "$RUN_AFTER" -eq 1 ]]; then
    say "Launching Thaw Preview…"
    open "$DEST"
    echo ""
    echo "First launch: grant Accessibility + Screen Recording permissions"
    echo "in System Settings → Privacy & Security."
else
    echo ""
    say "Done! Thaw Preview installed at: $DEST"
    echo "Launch with: open \"$DEST\""
    echo ""
    echo "First launch: grant Accessibility + Screen Recording permissions"
    echo "in System Settings → Privacy & Security."
fi
