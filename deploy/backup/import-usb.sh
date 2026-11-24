#!/usr/bin/env bash
# import-usb.sh -- stage archives from a stick, verified, and restore nothing.
# A16, agreed 2026-11-24.
#
# Staging is deliberate. A restore stops services, swaps files and starts them
# again; an appliance that does that because somebody inserted a stick is how a
# shift disappears. So this verifies, copies into place, and stops, printing the
# archives now available so the operator can choose one. The owner's requirement
# is in the last line of output: any archive, not only the newest, because
# discovering three days later that the wrong thing was running is exactly when
# an older copy is wanted.
#
# It reads the manifest the export wrote rather than guessing which archive
# belongs to which product, and it refuses a manifest that names a destination
# this appliance does not own. A device does not get to choose where files land.
#
# Run: sudo deploy/backup/import-usb.sh
set -euo pipefail

APPLIANCE_BACKUP_DIR="${APPLIANCE_BACKUP_DIR:-/mnt/appliance-backup}"
KOORSUS_BACKUP_DIR="${KOORSUS_BACKUP_DIR:-/mnt/koorsus-backup}"
USB="${APPLIANCE_USB_DIR:-}"

log() { printf '%s %s\n' "$(date -Is)" "$*"; }

if [ "$(id -u)" -ne 0 ] && [ "${APPLIANCE_TEST_ROOT:-0}" != "1" ]; then
  log "FAIL  must run as root (APPLIANCE_TEST_ROOT=1 exists for filesystem tests only)"
  exit 1
fi

if [ -z "$USB" ]; then
  for d in /media/* /media/*/* /run/media/*/* /mnt/usb*; do
    if [ -d "$d" ] && mountpoint -q "$d" 2>/dev/null; then USB="$d"; break; fi
  done
fi
if [ -z "$USB" ] || [ ! -d "$USB" ]; then
  log "FAIL  no mounted USB device found"
  exit 1
fi

MANIFEST="${USB}/MANIFEST.txt"
if [ ! -f "$MANIFEST" ]; then
  log "FAIL  no MANIFEST.txt on ${USB}"
  log "      Archives without a manifest cannot say which product they belong to,"
  log "      and a Koorsus index staged into the appliance directory makes the next"
  log "      restore report success while serving old data. Refusing."
  exit 1
fi

staged=0
failed=0
product=""; archive=""; source_dir=""; sum=""

flush() {
  [ -n "$product" ] || return 0
  if [ -z "$archive" ] || [ -z "$source_dir" ] || [ -z "$sum" ]; then
    log "WARN  incomplete manifest entry for ${product}"
    failed=$((failed + 1)); return 0
  fi
  case "$source_dir" in
    "$APPLIANCE_BACKUP_DIR"|"$KOORSUS_BACKUP_DIR") ;;
    *)
      log "FAIL  ${product} names source_dir=${source_dir}, which is not a backup directory here"
      log "      refusing to write where a device tells it to"
      failed=$((failed + 1)); return 0 ;;
  esac
  if [ ! -f "${USB}/${archive}" ]; then
    log "FAIL  ${archive} is listed in the manifest but is not on ${USB}"
    failed=$((failed + 1)); return 0
  fi
  if [ ! -f "${USB}/${archive}.sha256" ]; then
    log "FAIL  ${archive} has no checksum on the device; refusing to stage it unverified"
    failed=$((failed + 1)); return 0
  fi
  if ! ( cd "$USB" && sha256sum -c "${archive}.sha256" >/dev/null 2>&1 ); then
    log "FAIL  ${archive} fails its checksum on the device; the copy is damaged"
    failed=$((failed + 1)); return 0
  fi
  cp -f "${USB}/${archive}" "${USB}/${archive}.sha256" "${source_dir}/"
  if ! ( cd "${source_dir}" && sha256sum -c "${archive}.sha256" >/dev/null 2>&1 ); then
    log "FAIL  ${archive} did not verify after staging"
    failed=$((failed + 1)); return 0
  fi
  log "OK    staged ${product}: ${archive} -> ${source_dir}"
  staged=$((staged + 1))
}

while IFS='=' read -r key value; do
  case "$key" in
    ''|'#'*) continue ;;
    product) flush; product="$value"; archive=""; source_dir=""; sum="" ;;
    archive) archive="$value" ;;
    source_dir) source_dir="$value" ;;
    sha256) sum="$value" ;;
  esac
done < "$MANIFEST"
flush

if [ "$staged" -gt 0 ]; then
  log "DONE  ${staged} archive(s) staged and verified. NOTHING HAS BEEN RESTORED."
  log "      Myarra appliance, newest first, restore any of them:"
  ls -1t "${APPLIANCE_BACKUP_DIR}"/myarra-*.tar.gz.enc 2>/dev/null | sed 's/^/        /' || true
  log "      restore with:  sudo deploy/backup/restore.sh            (newest)"
  log "                     sudo deploy/backup/restore.sh <archive>   (any other)"
  log "      Koorsus index, newest first:"
  ls -1t "${KOORSUS_BACKUP_DIR}"/koorsus-*.tar.gz.enc 2>/dev/null | sed 's/^/        /' || true
  log "      restore with:  sudo /usr/local/sbin/koorsus/restore-index.sh"
  log "                     (set ARKIV_BACKUP_KEY=/etc/koorsus-backup.key first, see A53)"
fi

if [ "$failed" -gt 0 ]; then
  log "DONE  with ${failed} problem(s); ${staged} archive(s) staged"
  exit 2
fi
if [ "$staged" -eq 0 ]; then
  log "FAIL  nothing was staged"
  exit 1
fi
log "DONE  every manifest entry staged"
