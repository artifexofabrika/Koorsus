#!/bin/bash
# Koorsus restore -- REFUSES, on purpose. Written 2026-11-24.
#
# This file was a copy of the Arkiv restore script. It looked in
# /mnt/arkiv-backup for arkiv-*.tar.gz.enc, opened them with
# /etc/arkiv-backup.key, unpacked arkiv_index into /mnt/lake, and stopped and
# started arkiv.service. None of that is Koorsus: the Koorsus archives live in
# /mnt/koorsus-backup, are named koorsus-*.tar.gz.enc, are encrypted with
# /etc/koorsus-backup.key, and the service is koorsus-app.service. It was left
# behind by a rename that rebranded five of seven scripts and missed this one
# (A53).
#
# Run against a real Koorsus archive it failed at the key and reported "wrong
# passphrase or corrupt archive" about a perfectly good file, which is the worst
# message available during a recovery.
#
# Two working paths, both verified:
#
#   Koorsus index only:
#     sudo /usr/local/sbin/koorsus/restore-index.sh
#
#   The whole appliance -- Myarra database, Koorsus index and users, the units
#   and the TLS material, from one archive:
#     sudo /home/jeeves/Client-Demo/deploy/backup/restore.sh [archive]
#
# This stub stays so that whoever types restore.sh gets a true sentence instead
# of a failed decryption. It is deliberately not a working restore: the one it
# replaced belonged to another product.
set -euo pipefail

cat >&2 <<'MSG'
REFUSED. This is not a Koorsus restore script.

  The script that used to be here restores Arkiv: wrong directory, wrong
  archive prefix, wrong passphrase file, wrong service. It was left by a
  rename that never finished, and it cannot restore a Koorsus archive.

  Koorsus index:    sudo /usr/local/sbin/koorsus/restore-index.sh
  Whole appliance:  sudo /home/jeeves/Client-Demo/deploy/backup/restore.sh

  The passphrase is in deploy/ESCROW.md. The finding is A53 in deploy/AUDIT.md.
MSG
exit 1
