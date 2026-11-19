#!/bin/bash
# Appliance restore: Myarra + Koorsus from one archive.
#
# Every target path is prefixed with APPLIANCE_RESTORE_ROOT, empty in
# production, so a scratch-directory test runs the same code a real
# recovery runs.
#
# Services are stopped before files are swapped and started after. The
# original koorsus restore-index.sh deliberately did neither, which meant a
# running process kept reading the directory moved to .pre-restore and the
# restore reported success while serving stale data.
set -euo pipefail

BACKUP_DIR="${APPLIANCE_BACKUP_DIR:-/mnt/appliance-backup}"
KEY_FILE="${APPLIANCE_BACKUP_KEY:-/etc/koorsus-backup.key}"
LOG="${APPLIANCE_BACKUP_LOG:-/var/log/appliance-backup.log}"
MANIFEST="${APPLIANCE_MANIFEST:-/home/jeeves/Client-Demo/deploy/backup/artifacts.txt}"
ROOT="${APPLIANCE_RESTORE_ROOT:-}"
RESTART="${APPLIANCE_RESTORE_RESTART:-yes}"
SERVICES="${APPLIANCE_SERVICES:-koorsus-app.service myarr.service myarra-bot.service}"

log() { echo "$(date -Is) $*" | tee -a "$LOG"; }
fail() { log "FAIL  $*"; exit 1; }

ARCHIVE="${1:-}"
if [ -z "$ARCHIVE" ]; then
  ARCHIVE="$(ls -1t "${BACKUP_DIR}"/myarra-*.tar.gz.enc 2>/dev/null | head -1 || true)"
fi
[ -n "$ARCHIVE" ] || fail "no archive found in $BACKUP_DIR"
[ -f "${ARCHIVE}.sha256" ] || fail "checksum file missing: ${ARCHIVE}.sha256"
[ -r "$KEY_FILE" ] || fail "key not readable: $KEY_FILE"

log "RESTORE $(basename "$ARCHIVE") root=${ROOT:-/}"
( cd "$(dirname "$ARCHIVE")" && sha256sum -c "$(basename "${ARCHIVE}.sha256")" >/dev/null ) \
  || fail "checksum mismatch, refusing to restore"
log "OK    checksum matches"

WORK="$(mktemp -d)"
ARCH_TMP="$(mktemp -t appliance-restore-XXXXXX.tar.gz)"
cleanup() { rm -rf "$WORK"; rm -f "$ARCH_TMP"; }
trap cleanup EXIT

openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in "$ARCHIVE" -out "$ARCH_TMP" -pass "file:${KEY_FILE}" || fail "decryption failed"
log "OK    decrypted"

tar -xzf "$ARCH_TMP" -C "$WORK" || fail "extract failed"
[ -f "${WORK}/VERSIONS.txt" ] || fail "archive has no VERSIONS.txt"
log "OK    archive versions: $(tr '\n' ' ' < "${WORK}/VERSIONS.txt")"

STAMP="$(date +%Y%m%d-%H%M%S)"
SAFETY="${BACKUP_DIR}/pre-restore-${STAMP}"
mkdir -p "$SAFETY"

if [ -z "$ROOT" ] && [ "$RESTART" = "yes" ]; then
  log "STOP  ${SERVICES}"
  systemctl stop $SERVICES || fail "could not stop services, nothing was changed"
fi

while IFS=: read -r type owner path; do
  case "$type" in ''|\#*) continue ;; esac
  src="${WORK}/${owner}/$(basename "$path")"
  dst="${ROOT}${path}"
  if [ ! -e "$src" ]; then log "SKIP  not in archive: ${path}"; continue; fi
  mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ]; then
    mkdir -p "${SAFETY}$(dirname "$path")"
    mv "$dst" "${SAFETY}${path}"
  fi
  mv "$src" "$dst"
  log "OK    restored ${path}"
done < "$MANIFEST"

if [ -z "$ROOT" ] && [ "$RESTART" = "yes" ]; then
  log "START ${SERVICES}"
  systemctl start $SERVICES || fail "services failed to start after restore"
fi

while IFS=: read -r type owner path; do
  case "$type" in SQLITE) ;; *) continue ;; esac
  f="${ROOT}${path}"
  [ -f "$f" ] || continue
  r="$(sqlite3 "$f" 'PRAGMA integrity_check;' 2>&1 || echo ERROR)"
  [ "$r" = "ok" ] || fail "integrity check on ${path}: $r"
  log "OK    integrity ${path}: ok"
done < "$MANIFEST"

log "DONE  restored to root=${ROOT:-/}; pre-restore copies, if any, in ${SAFETY}"
