#!/usr/bin/env bash
# Copy the newest Arkiv archive to a mounted USB device and verify it.
set -euo pipefail

BACKUP_DIR=/mnt/koorsus-backup
log() { printf '%s %s\n' "$(date -Is)" "$*"; }

[ "$(id -u)" -eq 0 ] || { log "FAIL  must run as root"; exit 1; }

DEV=""
for d in /media/* /media/*/* /run/media/*/* /mnt/usb*; do
  if [ -d "$d" ] && mountpoint -q "$d"; then DEV="$d"; break; fi
done
[ -n "$DEV" ] || { log "FAIL  no mounted USB device found"; exit 1; }

NEWEST="$(find "$BACKUP_DIR" -maxdepth 1 -name '*.enc' \
  -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
[ -n "$NEWEST" ] || { log "FAIL  no archives in $BACKUP_DIR"; exit 1; }

BASE="$(basename "$NEWEST")"
cp -f "$NEWEST" "$DEV/"
cp -f "${NEWEST}.sha256" "$DEV/"
( cd "$DEV" && sha256sum -c "${BASE}.sha256" >/dev/null )
chown jeeves:jeeves "$DEV/$BASE" "$DEV/${BASE}.sha256" 2>/dev/null || true
log "OK    copied $BASE to $DEV and verified"
