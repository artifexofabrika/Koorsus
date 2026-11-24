#!/bin/bash
# Arkiv backup: tar ChromaDB index, encrypt with office passphrase, checksum, retain 30.
set -euo pipefail

BACKUP_DIR="${ARKIV_BACKUP_DIR:-/mnt/koorsus-backup}"
SOURCE="${ARKIV_INDEX_DIR:-/mnt/lake/koorsus_index}"
KEY_FILE="${ARKIV_BACKUP_KEY:-/etc/koorsus-backup.key}"
LOG="${ARKIV_BACKUP_LOG:-/var/log/koorsus-backup.log}"
KEEP="${ARKIV_BACKUP_KEEP:-30}"

ts="$(date +%Y%m%d-%H%M%S)"
tar_tmp="$(mktemp -t koorsus-${ts}-XXXXXX.tar.gz)"
out="${BACKUP_DIR}/koorsus-${ts}.tar.gz.enc"
sum="${out}.sha256"

log() { echo "$(date -Is) $*" | tee -a "$LOG"; }
cleanup() { rm -f "$tar_tmp" 2>/dev/null || true; }
trap cleanup EXIT

if [ ! -d "$BACKUP_DIR" ]; then log "ERROR: backup dir not found: $BACKUP_DIR"; exit 1; fi
if [ ! -d "$SOURCE" ]; then log "ERROR: source dir not found: $SOURCE"; exit 1; fi
if [ ! -r "$KEY_FILE" ]; then log "ERROR: passphrase file not readable: $KEY_FILE"; exit 1; fi

log "START backup ${out}"

tar -czf "$tar_tmp" -C "$(dirname "$SOURCE")" "$(basename "$SOURCE")"
tar_size=$(du -h "$tar_tmp" | cut -f1)

openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
  -in "$tar_tmp" -out "$out" -pass "file:${KEY_FILE}"

( cd "$BACKUP_DIR" && sha256sum "$(basename "$out")" > "$(basename "$sum")" )
enc_size=$(du -h "$out" | cut -f1)

log "OK    wrote $(basename "$out") (tar ${tar_size}, enc ${enc_size})"
log "OK    wrote $(basename "$sum")"

count=$(ls -1 "${BACKUP_DIR}"/koorsus-*.tar.gz.enc 2>/dev/null | wc -l)
if [ "$count" -gt "$KEEP" ]; then
  ls -1t "${BACKUP_DIR}"/koorsus-*.tar.gz.enc | tail -n +$((KEEP+1)) | while read -r f; do
    rm -f "$f" "${f}.sha256"
    log "PRUNE removed $(basename "$f")"
  done
fi

log "DONE  total archives: $(ls -1 "${BACKUP_DIR}"/koorsus-*.tar.gz.enc 2>/dev/null | wc -l)"
