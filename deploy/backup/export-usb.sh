#!/usr/bin/env bash
# export-usb.sh -- carry both products' newest archives off the box, verified.
# A16, agreed 2026-11-24.
#
# The appliance and the Koorsus index are backed up on different schedules into
# different directories, and only the Koorsus one ever had a USB path, so Myarra
# had no offsite copy at all. This carries both. Three rules it follows:
#
#  - The newest archive of each product, with its .sha256, verified after the
#    copy. A stick that was pulled early looks exactly like a good one until
#    somebody checks the hash on the day they need it.
#  - A manifest, because the import must never guess which archive belongs to
#    which product. Guessing is how a Koorsus index lands in the appliance
#    directory and the next restore reports success while serving old data.
#  - The passphrase never travels. A key stored with the ciphertext is one loss
#    rather than two, which is the whole of A14. If a key file is found on the
#    device the export refuses rather than tidying up behind someone.
#
# Run: sudo deploy/backup/export-usb.sh
set -euo pipefail

APPLIANCE_BACKUP_DIR="${APPLIANCE_BACKUP_DIR:-/mnt/appliance-backup}"
KOORSUS_BACKUP_DIR="${KOORSUS_BACKUP_DIR:-/mnt/koorsus-backup}"
USB="${APPLIANCE_USB_DIR:-}"
STALE_DAYS="${APPLIANCE_USB_STALE_DAYS:-2}"

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

if compgen -G "${USB}/*backup*.key" >/dev/null; then
  log "FAIL  a passphrase file is on ${USB}"
  log "      The key must not travel with the archives. Remove it, remove the"
  log "      archives it protects, and run this again."
  exit 1
fi

MANIFEST="${USB}/MANIFEST.txt"
{
  echo "# Myarra appliance export"
  echo "# written=$(date -Is) by export-usb.sh"
  echo "# The passphrase that opens these archives is NOT on this device."
  echo "# Stage them back with deploy/backup/import-usb.sh, then restore with"
  echo "#   deploy/backup/restore.sh [archive]   -- no argument means newest"
} > "$MANIFEST"

missing=0
for spec in "myarra:${APPLIANCE_BACKUP_DIR}" "koorsus:${KOORSUS_BACKUP_DIR}"; do
  product="${spec%%:*}"
  dir="${spec#*:}"
  newest="$(ls -1t "${dir}/${product}-"*.tar.gz.enc 2>/dev/null | head -1 || true)"

  if [ -z "$newest" ]; then
    log "WARN  no ${product} archive in ${dir}"
    missing=$((missing + 1))
    continue
  fi
  base="$(basename "$newest")"
  if [ ! -f "${newest}.sha256" ]; then
    log "WARN  ${base} has no .sha256; refusing to carry it unverified"
    missing=$((missing + 1))
    continue
  fi

  cp -f "$newest" "${newest}.sha256" "$USB/"
  if ! ( cd "$USB" && sha256sum -c "${base}.sha256" >/dev/null 2>&1 ); then
    log "FAIL  ${base} did not verify after the copy; treat this stick as unreliable"
    exit 1
  fi

  age_days=$(( ( $(date +%s) - $(stat -c %Y "$newest") ) / 86400 ))
  log "OK    ${product}: ${base} ($(du -h "$newest" | cut -f1)), ${age_days}d old"
  if [ "$age_days" -gt "$STALE_DAYS" ]; then
    log "WARN  ${product} archive is ${age_days} days old: the schedule that writes it is not running"
  fi

  {
    echo "product=${product}"
    echo "archive=${base}"
    echo "source_dir=${dir}"
    echo "sha256=$(cut -d' ' -f1 "${newest}.sha256")"
    echo "exported=$(date -Is)"
    echo
  } >> "$MANIFEST"
done

if [ "$missing" -gt 0 ]; then
  log "DONE  with ${missing} product(s) not carried; this device is not a complete offsite copy"
  exit 2
fi
log "DONE  both products on ${USB}, manifest written"
