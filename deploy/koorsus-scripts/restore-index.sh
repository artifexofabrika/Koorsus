#!/usr/bin/env bash
# Restore the newest Arkiv backup into the live index.
# Deliberately does NOT touch systemd: the web app reloads its store.
set -euo pipefail

BACKUP_DIR=/mnt/koorsus-backup
KEY_FILE=/etc/koorsus-backup.key
LAKE=/mnt/lake
INDEX_NAME=koorsus_index
LIVE="${LAKE}/${INDEX_NAME}"
SAFETY="${LAKE}/${INDEX_NAME}.pre-restore.$(date +%Y%m%d-%H%M%S)"

log() { printf '%s %s\n' "$(date -Is)" "$*"; }

[ "$(id -u)" -eq 0 ] || { log "FAIL  must run as root"; exit 1; }

BACKUP="$(find "$BACKUP_DIR" -maxdepth 1 -name '*.enc' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-)"
[ -n "$BACKUP" ] || { log "FAIL  no archives found in $BACKUP_DIR"; exit 1; }
SUM_FILE="${BACKUP}.sha256"
[ -f "$SUM_FILE" ] || { log "FAIL  checksum file missing"; exit 1; }

log "RESTORE $(basename "$BACKUP")"
if ! ( cd "$BACKUP_DIR" && sha256sum -c "$(basename "$SUM_FILE")" >/dev/null 2>&1 ); then
  log "FAIL  checksum mismatch. Refusing to restore."
  exit 1
fi
log "OK    checksum matches"

DECRYPTED="$(mktemp -t koorsus-restore-XXXXXX.tar.gz)"
WORKDIR="$(mktemp -d)"
cleanup() { rm -f "$DECRYPTED"; rm -rf "$WORKDIR"; }
trap cleanup EXIT

if ! openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
       -in "$BACKUP" -out "$DECRYPTED" -pass "file:${KEY_FILE}"; then
  log "FAIL  decryption failed."
  exit 1
fi
log "OK    decrypted"

tar -xzf "$DECRYPTED" -C "$WORKDIR"
[ -d "$WORKDIR/$INDEX_NAME" ] || { log "FAIL  archive lacks ${INDEX_NAME}/"; exit 1; }

if [ -e "$LIVE" ]; then
  mv "$LIVE" "$SAFETY"
  log "OK    previous index kept at $SAFETY"
fi
mv "$WORKDIR/$INDEX_NAME" "$LIVE"
chown -R jeeves:jeeves "$LIVE"
log "DONE  restore complete; previous index at $SAFETY"
