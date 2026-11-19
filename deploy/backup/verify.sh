#!/bin/bash
# Appliance backup verification: prove the newest archive is restorable.
#
# Strict by design. The nightly archive is allowed to differ from live,
# because hours and documents are written after the backup runs. What is
# not allowed is an archive that will not decrypt, will not extract, or
# fails a SQLite integrity check. Any of those is a hard failure.
set -euo pipefail

BACKUP_DIR="${APPLIANCE_BACKUP_DIR:-/mnt/appliance-backup}"
KEY_FILE="${APPLIANCE_BACKUP_KEY:-/etc/koorsus-backup.key}"
LOG="${APPLIANCE_BACKUP_LOG:-/var/log/appliance-backup.log}"
MANIFEST="${APPLIANCE_MANIFEST:-/home/jeeves/Client-Demo/deploy/backup/artifacts.txt}"
STATUS="${APPLIANCE_VERIFY_STATUS:-/var/log/appliance-verify.status}"

log() { echo "$(date -Is) $*" | tee -a "$LOG"; }
fail() { log "FAIL  $*"; echo "FAIL|$(date -Is)|$*" > "$STATUS"; exit 1; }
ok()   { log "OK    $*"; }

[ "$(id -u)" -eq 0 ] || fail "must run as root"

ARCHIVE="$(ls -1t "${BACKUP_DIR}"/myarra-*.tar.gz.enc 2>/dev/null | head -1 || true)"
[ -n "$ARCHIVE" ] || fail "no archive found in $BACKUP_DIR"
[ -f "${ARCHIVE}.sha256" ] || fail "checksum missing for $(basename "$ARCHIVE")"
[ -r "$KEY_FILE" ] || fail "key not readable: $KEY_FILE"

log "VERIFY $(basename "$ARCHIVE")"
( cd "$(dirname "$ARCHIVE")" && sha256sum -c "$(basename "${ARCHIVE}.sha256")" >/dev/null ) \
  || fail "checksum mismatch"
ok "checksum matches"

WORK="$(mktemp -d)"
TMP="$(mktemp -t appliance-verify-XXXXXX.tar.gz)"
cleanup() { rm -rf "$WORK"; rm -f "$TMP"; }
trap cleanup EXIT

openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -in "$ARCHIVE" -out "$TMP" -pass "file:${KEY_FILE}" || fail "decryption failed"
ok "decryption succeeded"

tar -xzf "$TMP" -C "$WORK" || fail "decrypted data is not a valid tar.gz"
[ -f "${WORK}/VERSIONS.txt" ] || fail "archive has no VERSIONS.txt"
ok "versions: $(tr '\n' ' ' < "${WORK}/VERSIONS.txt")"

while IFS=: read -r type owner path; do
  case "$type" in SQLITE) ;; *) continue ;; esac
  f="${WORK}/${owner}/$(basename "$path")"
  [ -f "$f" ] || fail "archive missing ${owner}/$(basename "$path")"
  r="$(sqlite3 "$f" 'PRAGMA integrity_check;' 2>&1 || echo ERROR)"
  [ "$r" = "ok" ] || fail "integrity ${path}: $r"
  ok "integrity ${owner}/$(basename "$path"): ok"
done < "$MANIFEST"

CHROMA="${WORK}/koorsus/koorsus_index/chroma.sqlite3"
if [ -f "$CHROMA" ]; then
  r="$(sqlite3 "$CHROMA" 'PRAGMA integrity_check;' 2>&1 || echo ERROR)"
  [ "$r" = "ok" ] || fail "integrity koorsus_index/chroma.sqlite3: $r"
  ok "integrity koorsus_index/chroma.sqlite3: ok"
fi

MY="${WORK}/myarra/myarra.db"
if [ -f "$MY" ]; then
  c="$(sqlite3 "$MY" "SELECT (SELECT COUNT(*) FROM jobs)||' jobs, '||(SELECT COUNT(*) FROM hourly_runs)||' hours, '||(SELECT COUNT(*) FROM line_events)||' line events';" 2>&1 || echo ERROR)"
  ok "myarra content: ${c}"
fi

echo "OK|$(date -Is)|$(basename "$ARCHIVE") verified" > "$STATUS"
log "DONE  $(basename "$ARCHIVE") is restorable"
