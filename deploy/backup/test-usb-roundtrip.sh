#!/usr/bin/env bash
# test-usb-roundtrip.sh -- the offsite path, proven without root, a stick or a key.
#
# A16. Both scripts take their directories from the environment and refuse to run
# as a normal user unless APPLIANCE_TEST_ROOT=1, which exists so this test can
# exercise the real code rather than a copy of its logic. Nothing here decrypts
# anything: the archives are stand-ins, and the subject is placement, manifests,
# checksums and refusal.
#
# Run: bash deploy/backup/test-usb-roundtrip.sh
# Exit 0 when every check passes, 1 when any fails.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
EXPORT="$HERE/export-usb.sh"
IMPORT="$HERE/import-usb.sh"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

src_a="$work/appliance"
src_k="$work/koorsus"
usb="$work/usb"
mkdir -p "$src_a" "$src_k" "$usb"

fails=0
checks=0
check() {
  checks=$((checks + 1))
  if [ "$2" = "$3" ]; then
    echo "PASS  $1"
  else
    echo "FAIL  $1"
    echo "        got:      $2"
    echo "        wanted:   $3"
    fails=$((fails + 1))
  fi
}
contains() { case "$2" in *"$1"*) echo yes ;; *) echo no ;; esac; }

run_export() {
  APPLIANCE_TEST_ROOT=1 APPLIANCE_BACKUP_DIR="$src_a" \
  KOORSUS_BACKUP_DIR="$src_k" APPLIANCE_USB_DIR="$usb" bash "$EXPORT"
}
run_import() {
  APPLIANCE_TEST_ROOT=1 APPLIANCE_BACKUP_DIR="$src_a" \
  KOORSUS_BACKUP_DIR="$src_k" APPLIANCE_USB_DIR="$usb" bash "$IMPORT"
}

make_archive() {  # dir, basename
  printf 'stand-in archive %s\n' "$2" > "$1/$2"
  ( cd "$1" && sha256sum "$2" > "$2.sha256" )
}

NEW_A='myarra-20261124-033407.tar.gz.enc'
OLD_A='myarra-20261101-033000.tar.gz.enc'
KOR='koorsus-20261117-104125.tar.gz.enc'

make_archive "$src_a" "$NEW_A"
make_archive "$src_a" "$OLD_A"
touch -d '20 days ago' "$src_a/$OLD_A"
make_archive "$src_k" "$KOR"
touch -d '9 days ago' "$src_k/$KOR"
# A key left lying in a backup directory, which is exactly the mistake the export
# exists to refuse.
printf 'this must never travel\n' > "$src_a/koorsus-backup.key"

check "export-usb.sh is executable" "$([ -x "$EXPORT" ] && echo yes || echo no)" "yes"
check "import-usb.sh is executable" "$([ -x "$IMPORT" ] && echo yes || echo no)" "yes"

# ---- export
out="$(run_export 2>&1)"; rc=$?
check "export exits 0 when both products have an archive" "$rc" "0"
check "it carries the newest appliance archive, not the oldest" \
      "$([ -f "$usb/$NEW_A" ] && [ ! -f "$usb/$OLD_A" ] && echo yes || echo no)" "yes"
check "it carries the koorsus archive too" "$([ -f "$usb/$KOR" ] && echo yes || echo no)" "yes"
check "it writes a manifest naming both products" \
      "$(contains 'product=myarra' "$(cat "$usb/MANIFEST.txt")")$(contains 'product=koorsus' "$(cat "$usb/MANIFEST.txt")")" \
      "yesyes"
check "the passphrase does not travel with the archives" \
      "$(ls "$usb" | grep -c 'backup.*\.key' || true)" "0"
check "it warns that an archive is older than the schedule allows" \
      "$(contains 'days old' "$out")" "yes"

# ---- export must refuse a device that already carries a key
printf 'stray key\n' > "$usb/koorsus-backup.key"
out="$(run_export 2>&1)"; rc=$?
check "export refuses a device that already carries a passphrase file" "$rc" "1"
check "it says why, in those words" \
      "$(contains 'passphrase file is on' "$out")" "yes"
rm -f "$usb/koorsus-backup.key"

# clean manifest for the import tests
run_export >/dev/null 2>&1

# ---- import stages, verifies, and does not restore
rm -f "$src_a/$NEW_A" "$src_a/$NEW_A.sha256" "$src_k/$KOR" "$src_k/$KOR.sha256"
out="$(run_import 2>&1)"; rc=$?
check "import exits 0 with a clean manifest" "$rc" "0"
check "it stages the appliance archive back into place" \
      "$([ -f "$src_a/$NEW_A" ] && echo yes || echo no)" "yes"
check "it stages the koorsus archive back into place" \
      "$([ -f "$src_k/$KOR" ] && echo yes || echo no)" "yes"
check "it restores nothing by itself" \
      "$(contains 'NOTHING HAS BEEN RESTORED' "$out")" "yes"
check "it lists what can be restored, including the older archive" \
      "$(contains "$OLD_A" "$out")" "yes"
check "it says how to restore an archive that is not the newest" \
      "$(contains 'restore.sh <archive>' "$out")" "yes"

# ---- a manifest that names a destination this appliance does not own
cp "$usb/MANIFEST.txt" "$work/manifest.good"
printf 'product=myarra\narchive=%s\nsource_dir=/tmp/elsewhere\nsha256=deadbeef\n\n' "$NEW_A" > "$usb/MANIFEST.txt"
out="$(run_import 2>&1)"; rc=$?
check "import refuses a manifest that names a foreign destination" "$rc" "2"
check "it says the device does not get to choose where files land" \
      "$(contains 'not a backup directory here' "$out")" "yes"

# ---- a damaged archive on the device
cp "$work/manifest.good" "$usb/MANIFEST.txt"
printf 'x' >> "$usb/$NEW_A"
out="$(run_import 2>&1)"; rc=$?
check "import refuses an archive whose checksum does not match" "$rc" "2"
check "it says the copy is damaged rather than the key being wrong" \
      "$(contains 'fails its checksum on the device' "$out")" "yes"

echo ""
echo "$checks checks, $fails failed"
[ "$fails" -eq 0 ]
