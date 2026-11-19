#!/bin/bash
# Appliance backup: Myarra + Koorsus, one archive, one manifest.
#
# Design notes:
#  - SQLITE artifacts are copied with sqlite3 .backup, not cp, so an operator
#    logging an hour cannot produce a torn snapshot.
#  - DIR artifacts are copied as-is. Chroma's sqlite inside the index is
#    expected to be idle at 03:30; this is the same assumption the existing
#    verified koorsus backup makes at 03:00.
#  - A missing artifact is a WARN and a non-zero exit, not a silent omission.
#  - The archive lands on the same filesystem as the data. It protects against
#    deletion and corruption, not disk failure. The USB export is the offsite
#    path and it needs a person.
set -euo pipefail

BACKUP_DIR="${APPLIANCE_BACKUP_DIR:-/mnt/appliance-backup}"
KEY_FILE="${APPLIANCE_BACKUP_KEY:-/etc/koorsus-backup.key}"
LOG="${APPLIANCE_BACKUP_LOG:-/var/log/appliance-backup.log}"
KEEP="${APPLIANCE_BACKUP_KEEP:-30}"
MANIFEST="${APPLIANCE_MANIFEST:-/home/jeeves/Client-Demo/deploy/backup/artifacts.txt}"

log() { echo "$(date -Is) $*" | tee -a "$LOG"; }

for p in "$BACKUP_DIR" "$KEY_FILE" "$MANIFEST"; do
  [ -e "$p" ] || { log "ERROR: missing $p"; exit 1; }
done

ts="$(date +%Y%m%d-%H%M%S)"
out="${BACKUP_DIR}/myarra-${ts}.tar.gz.enc"
sum="${out}.sha256"
STAGE="$(mktemp -d)"
tar_tmp="$(mktemp -t appliance-${ts}-XXXXXX.tar.gz)"
cleanup() { rm -rf "$STAGE"; rm -f "$tar_tmp"; }
trap cleanup EXIT

missing=0
log "START backup $(basename "$out")"

while IFS=: read -r type owner path; do
  case "$type" in ''|\#*) continue ;; esac
  if [ ! -e "$path" ]; then
    log "WARN  missing ${type}:${owner}:${path}"
    missing=$((missing + 1))
    continue
  fi
  dest="${STAGE}/${owner}"
  mkdir -p "$dest"
  name="$(basename "$path")"
  case "$type" in
    SQLITE)
      sqlite3 "$path" ".backup '${dest}/${name}'"
      log "OK    sqlite ${owner}/${name}"
      ;;
    FILE)
      cp -p "$path" "${dest}/${name}"
      log "OK    file   ${owner}/${name}"
      ;;
    DIR)
      cp -a "$path" "${dest}/${name}"
      log "OK    dir    ${owner}/${name} ($(du -sh "${dest}/${name}" | cut -f1))"
      ;;
    *)
      log "WARN  unknown type ${type} for ${path}"
      missing=$((missing + 1))
      ;;
  esac
done < "$MANIFEST"

{
  echo "created=$(date -Is)"
  echo "host=$(hostname)"
  for repo in /home/jeeves/Client-Demo /home/jeeves/koorsus; do
    if [ -d "${repo}/.git" ]; then
      echo "$(basename "$repo")=$(git -C "$repo" rev-parse HEAD 2>/dev/null || echo unknown)"
    fi
  done
} > "${STAGE}/VERSIONS.txt"

tar -czf "$tar_tmp" -C "$STAGE" .
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
  -in "$tar_tmp" -out "$out" -pass "file:${KEY_FILE}"
( cd "$BACKUP_DIR" && sha256sum "$(basename "$out")" > "$(basename "$sum")" )
log "OK    wrote $(basename "$out") ($(du -h "$out" | cut -f1)), $(basename "$sum")"

count=$(ls -1 "${BACKUP_DIR}"/myarra-*.tar.gz.enc 2>/dev/null | wc -l)
if [ "$count" -gt "$KEEP" ]; then
  ls -1t "${BACKUP_DIR}"/myarra-*.tar.gz.enc | tail -n +$((KEEP + 1)) | while read -r f; do
    rm -f "$f" "${f}.sha256"
    log "PRUNE removed $(basename "$f")"
  done
fi

if [ "$missing" -gt 0 ]; then
  log "DONE  with ${missing} missing artifact(s); archive is incomplete"
  exit 2
fi
log "DONE  complete, total archives: $(ls -1 "${BACKUP_DIR}"/myarra-*.tar.gz.enc 2>/dev/null | wc -l)"
