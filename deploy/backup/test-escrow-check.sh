#!/usr/bin/env bash
# test-escrow-check.sh -- the escrow tool, proven without an appliance.
#
# A14's whole risk is that escrow is documentation nobody exercised. A script
# that is never run against a real archive, with a real typed passphrase, tests
# nothing. This builds its own archive with a known passphrase and asserts the
# four outcomes that matter: the right passphrase passes and reads the manifest
# inside, a wrong one fails without pretending the file is damaged, a damaged
# file fails as damaged rather than as mis-keyed, and a missing file refuses.
#
# No root, no /etc, no USB, no appliance.
#
# Run: bash deploy/backup/test-escrow-check.sh
# Exit 0 when every check passes, 1 when any fails.

set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TOOL="$HERE/escrow-check.sh"
PASS='correct horse battery staple'
BASE='myarra-20261124-033000.tar.gz.enc'

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

fails=0
checks=0
check() {  # name, actual, expected
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
contains() {  # needle, haystack
  case "$2" in *"$1"*) echo yes ;; *) echo no ;; esac
}

check "the tool exists and is executable" \
      "$([ -x "$TOOL" ] && echo yes || echo no)" "yes"

# ---- 0. the checker and the producer must agree on the cipher.
# A fixture that the checker both wrote and read proves nothing about the
# archives backup.sh actually produces. These two tokens are the ones that would
# silently diverge, and a mismatch would open a test archive and refuse a real one.
producer="$HERE/backup.sh"
if [ -f "$producer" ]; then
  for token in '-aes-256-cbc' '200000'; do
    check "escrow-check and backup.sh agree on $token" \
          "$(contains "$token" "$(cat "$producer")")$(contains "$token" "$(cat "$TOOL")")" \
          "yesyes"
  done
fi

# ---- fixture: a small archive that looks like the real thing
mkdir -p "$work/stage/myarra"
printf 'created=2026-11-24T03:30:00-05:00\nhost=koorsus\nClient-Demo=3588dd4\n' \
  > "$work/stage/VERSIONS.txt"
printf 'not a database, just a file with the right name\n' \
  > "$work/stage/myarra/myarra.db"
tar -czf "$work/plain.tar.gz" -C "$work/stage" .
printf '%s' "$PASS" > "$work/key"
openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
  -in "$work/plain.tar.gz" -out "$work/$BASE" -pass "file:$work/key"
( cd "$work" && sha256sum "$BASE" > "${BASE}.sha256" )

# ---- 1. the right passphrase
out="$(ESCROW_PASS="$PASS" "$TOOL" "$work/$BASE" 2>&1)"; rc=$?
check "the right passphrase exits 0" "$rc" "0"
check "it says the escrow copy is usable" \
      "$(contains 'PASS  this passphrase opens' "$out")" "yes"
check "it reads the manifest from inside the archive" \
      "$(contains 'host=koorsus' "$out")" "yes"

# ---- 2. a wrong passphrase
out="$(ESCROW_PASS='not the passphrase' "$TOOL" "$work/$BASE" 2>&1)"; rc=$?
check "a wrong passphrase exits 1" "$rc" "1"
check "it says the passphrase does not open the archive" \
      "$(contains 'does not open' "$out")" "yes"
check "it does not blame the file when the key is wrong" \
      "$(contains 'damaged' "$out")" "no"

# ---- 3. a damaged file, with its checksum beside it
mkdir -p "$work/dmg"
cp "$work/$BASE" "$work/${BASE}.sha256" "$work/dmg/"
printf 'x' >> "$work/dmg/$BASE"
out="$(ESCROW_PASS="$PASS" "$TOOL" "$work/dmg/$BASE" 2>&1)"; rc=$?
check "a damaged archive exits 1" "$rc" "1"
check "it blames the file, not the passphrase" \
      "$(contains 'damaged or incomplete' "$out")" "yes"

# ---- 4. a missing file
out="$(ESCROW_PASS="$PASS" "$TOOL" "$work/nothing-here.tar.gz.enc" 2>&1)"; rc=$?
check "a missing archive exits 2" "$rc" "2"
check "it says which file it could not find" \
      "$(contains 'no such file' "$out")" "yes"

# ---- 5. no checksum beside the copy: it must still open, and say it is unchecked
cp "$work/$BASE" "$work/unchecked.tar.gz.enc"
out="$(ESCROW_PASS="$PASS" "$TOOL" "$work/unchecked.tar.gz.enc" 2>&1)"; rc=$?
check "an archive with no checksum still opens" "$rc" "0"
check "it says the integrity check was skipped" \
      "$(contains 'WARN  no .sha256' "$out")" "yes"

echo ""
echo "$checks checks, $fails failed"
[ "$fails" -eq 0 ]
