#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/devinmcnair/Desktop/ClubHub/backend"
PLIST_SOURCE="$ROOT/com.clubhub.sync.plist"
PLIST_TARGET="$HOME/Library/LaunchAgents/com.clubhub.sync.plist"

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/logs"
cp "$PLIST_SOURCE" "$PLIST_TARGET"
launchctl unload "$PLIST_TARGET" 2>/dev/null || true
launchctl load "$PLIST_TARGET"
launchctl start com.clubhub.sync

echo "Installed launchd sync job:"
echo "  $PLIST_TARGET"
echo "Check status with:"
echo "  launchctl list | grep clubhub"
