#!/usr/bin/env bash
# escrow-check.sh -- prove that a passphrase you can read off paper opens an
# archive you are holding. A14, agreed 2026-11-24.
#
# /etc/koorsus-backup.key encrypts every archive and is inside none of them,
# which is correct: a key stored beside its own ciphertext protects nothing. The
# price is that losing it turns thirty archives into unreadable noise with no
# recovery path. Escrow that has never been exercised is a hope, so this is the
# exercise. It needs no root, no appliance and no /etc: one archive, one
# passphrase typed by a human, and openssl.
#
#   ./escrow-check.sh /media/usb/myarra-20261124-033000.tar.gz.enc
#   ESCROW_PASS='...' ./escrow-check.sh archive.tar.gz.enc    # scripted use
#
# Exit 0 the passphrase opens the archive and the contents are a real backup,
#      1 the passphrase is wrong or the file is damaged,
#      2 it cannot start.
set -uo pipefail

ARCHIVE="${1:-}"
die() { echo "FAIL  $*" >&2; exit 2; }

[ -n "$ARCHIVE" ] || die "usage: $0 <archive.tar.gz.enc>"
[ -f "$ARCHIVE" ] || die "no such file: $ARCHIVE"
command -v openssl >/dev/null 2>&1 || die "openssl is not installed"
command -v tar >/dev/null 2>&1 || die "tar is not installed"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# 1. Integrity before decryption, so a damaged copy is never mistaken for a
#    wrong passphrase. The two failures need different actions: one means find
#    the other copy of the file, the other means find the other copy of the key.
if [ -f "${ARCHIVE}.sha256" ]; then
  if ! ( cd "$(dirname "$ARCHIVE")" \
         && sha256sum -c "$(basename "${ARCHIVE}").sha256" >/dev/null 2>&1 ); then
    echo "FAIL  checksum does not match $(basename "${ARCHIVE}").sha256" >&2
    echo "      The file is damaged or incomplete, not mis-keyed. Find another copy." >&2
    exit 1
  fi
  echo "OK    checksum matches"
else
  echo "WARN  no .sha256 beside the archive; integrity not checked"
fi

# 2. Decrypt. The passphrase comes from the environment when set, otherwise it is
#    typed. Neither leaves the key on disk, which is the point of the exercise.
if [ -n "${ESCROW_PASS:-}" ]; then
  pass_opt=(-pass env:ESCROW_PASS)
else
  printf 'Passphrase from the sealed copy: '
  IFS= read -rs PASS || true
  echo
  [ -n "${PASS:-}" ] || die "no passphrase entered"
  export PASS
  pass_opt=(-pass env:PASS)
fi

if ! openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
      -in "$ARCHIVE" -out "$work/backup.tar.gz" "${pass_opt[@]}" 2>"$work/err"; then
  echo "FAIL  this passphrase does not open this archive" >&2
  sed -n '1,2p' "$work/err" | sed 's/^/      /' >&2 || true
  echo "      Try the other escrow copy. If both fail, neither holds the" >&2
  echo "      passphrase this archive was written with." >&2
  exit 1
fi
echo "OK    decrypted"

# 3. Decrypted bytes are not the same as a backup. Insist on a gzip tar with the
#    manifest inside it, or say the archive is corrupt.
if ! tar -tzf "$work/backup.tar.gz" > "$work/list" 2>/dev/null; then
  echo "FAIL  decrypted, but the result is not a gzip tar: the archive is corrupt" >&2
  exit 1
fi
if ! grep -qx '\./VERSIONS.txt' "$work/list"; then
  echo "FAIL  decrypted, but carries no VERSIONS.txt: this is not an appliance archive" >&2
  exit 1
fi
echo "OK    a real archive: $(wc -l < "$work/list") entries, VERSIONS.txt present"

tar -xzf "$work/backup.tar.gz" -C "$work" ./VERSIONS.txt 2>/dev/null || true
if [ -s "$work/VERSIONS.txt" ]; then
  echo "      --- written inside the archive:"
  sed 's/^/      /' "$work/VERSIONS.txt"
fi

echo
echo "PASS  this passphrase opens $(basename "$ARCHIVE"). The escrow copy is usable."
