#!/bin/bash
# One-time backup encryption passphrase setup. Run as root at provisioning time.
#
# CORRECTED 2026-11-24 (A53). This defaulted to /etc/arkiv-backup.key while both
# backup scripts write with /etc/koorsus-backup.key, so running it produced a key
# that nothing read for backup and left the archives it was meant to protect
# unopenable by the restore path. The default now names the key the backups
# actually use. If a passphrase already exists there this refuses unless
# overwritten explicitly, because rotating it orphans every archive written with
# the old one: keep the old passphrase for as long as you keep them.
set -euo pipefail

KEY_FILE="${ARKIV_BACKUP_KEY:-/etc/koorsus-backup.key}"

if [ "$EUID" -ne 0 ]; then echo "ERROR: run with sudo."; exit 1; fi

if [ -f "$KEY_FILE" ]; then
  echo "Passphrase file already exists: $KEY_FILE"
  echo "Every archive already written is encrypted with it. Overwriting makes"
  echo "those archives unreadable unless you keep the old passphrase."
  read -r -p "Overwrite? (yes/NO) " ans
  [ "$ans" = "yes" ] || { echo "Aborted."; exit 1; }
fi

echo "Choose a backup encryption passphrase."
echo "Requirements: at least 16 characters, mix of letters, digits, symbols."
echo "This passphrase encrypts every backup. If it is lost, backups are unrecoverable."
echo "Store it in the firm's password manager. At least two staff should hold it."
echo "Then print one copy, seal it, and store it off site, apart from the archives."
echo "deploy/ESCROW.md in the Myarra repository says how, and how to prove it works."
echo

read -r -s -p "Passphrase: " p1; echo
read -r -s -p "Confirm:    " p2; echo

if [ "$p1" != "$p2" ]; then echo "Passphrases do not match."; exit 1; fi
if [ "${#p1}" -lt 16 ]; then echo "Passphrase must be at least 16 characters."; exit 1; fi

umask 077
printf '%s' "$p1" > "$KEY_FILE"
chown root:root "$KEY_FILE"
chmod 600 "$KEY_FILE"

echo
echo "Wrote $KEY_FILE (root-only)."
echo "Prove it before you trust it:"
echo "  sudo /home/jeeves/Client-Demo/deploy/backup/escrow-check.sh <archive>"
