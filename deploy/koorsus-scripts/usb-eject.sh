#!/usr/bin/env bash
set -euo pipefail
MOUNT=/mnt/usb
log() { printf '%s %s\n' "$(date -Is)" "$*"; }
[ "$(id -u)" -eq 0 ] || { log "FAIL  must run as root"; exit 1; }
if mountpoint -q "$MOUNT"; then
  sync
  systemctl stop mnt-usb.mount 2>/dev/null || umount "$MOUNT"
  log "OK    unmounted. Safe to remove the stick."
else
  log "OK    nothing is mounted there."
fi
