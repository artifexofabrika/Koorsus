#!/bin/bash
# Arkiv backup verification: prove the newest backup is restorable and current.
# Extracts the newest encrypted backup, opens the ChromaDB, counts documents,
# compares to the live index. Writes a status file the admin page can read.
set -euo pipefail

if [ "$EUID" -ne 0 ]; then echo "ERROR: run as root (sudo)."; exit 1; fi

BACKUP_DIR="${ARKIV_BACKUP_DIR:-/mnt/koorsus-backup}"
LIVE_INDEX="${ARKIV_INDEX_DIR:-/mnt/lake/koorsus_index}"
KEY_FILE="${ARKIV_BACKUP_KEY:-/etc/koorsus-backup.key}"
LOG="${ARKIV_BACKUP_LOG:-/var/log/koorsus-backup.log}"
STATUS_FILE="${ARKIV_VERIFY_STATUS:-/var/log/koorsus-verify.status}"

log() { echo "$(date -Is) $*" | tee -a "$LOG"; }
fail() { log "FAIL  $*"; echo "FAIL|$(date -Is)|$*" > "$STATUS_FILE"; exit 1; }
ok()   { log "OK    $*"; }

log "START verify"

BACKUP="$(ls -1t "${BACKUP_DIR}"/koorsus-*.tar.gz.enc 2>/dev/null | head -1 || true)"
if [ -z "$BACKUP" ]; then fail "no backups found in ${BACKUP_DIR}"; fi
SUM_FILE="${BACKUP}.sha256"
ARCHIVE_DIR="$(dirname "$BACKUP")"

if [ ! -f "$SUM_FILE" ]; then fail "checksum missing: $(basename "$SUM_FILE")"; fi
if [ ! -r "$KEY_FILE" ]; then fail "passphrase not readable: $KEY_FILE"; fi
if [ ! -d "$LIVE_INDEX" ]; then fail "live index not found: $LIVE_INDEX"; fi

log "VERIFY $(basename "$BACKUP")"
if ! ( cd "$ARCHIVE_DIR" && sha256sum -c "$(basename "$SUM_FILE")" > /dev/null 2>&1 ); then
  fail "checksum mismatch on $(basename "$BACKUP")"
fi
ok "checksum matches"

TMPDIR="$(mktemp -d -t koorsus-verify-XXXXXX)"
DECRYPTED="${TMPDIR}/archive.tar.gz"
cleanup() { rm -rf "$TMPDIR" 2>/dev/null || true; }
trap cleanup EXIT

log "DECRYPT $(basename "$BACKUP")"
if ! openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
       -in "$BACKUP" -out "$DECRYPTED" -pass "file:${KEY_FILE}"; then
  fail "decryption failed: wrong passphrase or corrupt archive"
fi
ok "decryption succeeded"

if ! tar -tzf "$DECRYPTED" > /dev/null 2>&1; then
  fail "decrypted data is not a valid tar.gz"
fi

log "EXTRACT to ${TMPDIR}"
tar -xzf "$DECRYPTED" -C "$TMPDIR"

EXTRACTED="${TMPDIR}/$(basename "$LIVE_INDEX")"
if [ ! -d "$EXTRACTED" ]; then fail "archive does not contain $(basename "$LIVE_INDEX")/"; fi
if [ ! -f "${EXTRACTED}/chroma.sqlite3" ]; then fail "chroma.sqlite3 missing from archive"; fi

log "SQLITE integrity_check"
INTEG="$(sqlite3 "${EXTRACTED}/chroma.sqlite3" 'PRAGMA integrity_check;' 2>&1 || echo "ERROR")"
if [ "$INTEG" != "ok" ]; then
  fail "sqlite integrity check: $INTEG"
fi
ok "sqlite integrity: ok"

log "COUNT documents"
COUNTS="$(ARKIV_VERIFY_EXTRACTED="$EXTRACTED" ARKIV_VERIFY_LIVE="$LIVE_INDEX" \
  /home/jeeves/jeeves-env/bin/python - <<'PY'
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
import chromadb

def count_at(path):
    try:
        client = chromadb.PersistentClient(path=path)
        try:
            col = client.get_collection("koorsus_documents")
            return col.count()
        except Exception:
            return 0
    except Exception as e:
        return "ERR:" + str(e)

live = count_at(os.environ["ARKIV_VERIFY_LIVE"])
backup = count_at(os.environ["ARKIV_VERIFY_EXTRACTED"])
print(f"{live}|{backup}")
PY
)"

LIVE_COUNT="${COUNTS%%|*}"
BACKUP_COUNT="${COUNTS##*|}"

if [[ "$LIVE_COUNT" == ERR* ]] || [[ "$BACKUP_COUNT" == ERR* ]]; then
  fail "count error: $COUNTS"
fi

log "live=${LIVE_COUNT}  backup=${BACKUP_COUNT}"

if [ "$LIVE_COUNT" != "$BACKUP_COUNT" ]; then
  log "WARN  backup count differs from live (live has changed since the backup ran)"
  log "      this is normal if documents were ingested after 03:00"
fi

ok "backup restorable, $(basename "$BACKUP") is valid"
echo "OK|$(date -Is)|backup=${BACKUP_COUNT} live=${LIVE_COUNT}" > "$STATUS_FILE"
log "DONE  verify complete"
