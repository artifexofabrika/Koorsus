#!/usr/bin/env bash
# Pull the newest archive from a mounted USB and restore it.
set -euo pipefail

BACKUP_DIR=/mnt/koorsus-backup
RESTORE=/usr/local/sbin/koorsus/restore-index.sh
log() { printf '%s %s\n' "$(date -Is)" "$*"; }

[ "$(id -u)" -eq 0 ] || { log "FAIL  must run as root"; exit 1; }

DEV=""
for d in /media/* /media/*/* /run/media/*/* /mnt/usb*; do
  if [ -d "$d" ] && mountpoint -q "$d"; then DEV="$d"; break; fi
done
[ -n "$DEV" ] || { log "FAIL  no mounted USB device found"; exit 1; }

NEWEST="$(find "$DEV" -maxdepth 1 -name '*.enc' \
  -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
[ -n "$NEWEST" ] || { log "FAIL  no archives on $DEV"; exit 1; }

BASE="$(basename "$NEWEST")"
[ -f "${NEWEST}.sha256" ] || { log "FAIL  checksum missing on USB"; exit 1; }
( cd "$DEV" && sha256sum -c "${BASE}.sha256" >/dev/null )
cp -f "$NEWEST" "$BACKUP_DIR/"
cp -f "${NEWEST}.sha256" "$BACKUP_DIR/"
chown jeeves:jeeves "$BACKUP_DIR/$BASE" "$BACKUP_DIR/${BASE}.sha256"
log "OK    imported $BASE from $DEV"
exec "$RESTORE"
