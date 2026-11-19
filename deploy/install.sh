#!/usr/bin/env bash
# Myarra appliance installer. Idempotent: safe to re-run on a provisioned board.
#
# Modes:
#   sudo bash install.sh              full appliance, Myarra and Koorsus
#   sudo bash install.sh --koorsus    Koorsus only, for a unit sold alone
#
# Structure deliberately mirrors the Arkiv installer: refuse on a failed
# precondition, never overwrite an existing config or passphrase, and install
# the certificate-dependent services last.
#
# pip needs the network. This runs on a provisioning bench, not at a plant.
# Volume units are cloned from a verified board.
set -euo pipefail

MODE=appliance
case "${1:-}" in
  --koorsus) MODE=koorsus ;;
  "") ;;
  *) echo "usage: $0 [--koorsus]"; exit 2 ;;
esac

REPO=/home/jeeves/Client-Demo
KOORSUS_APP=/home/jeeves/koorsus
SVC_USER=jeeves
VENV=/home/jeeves/jeeves-env
DATA_DIR=/mnt/lake
BACKUP_DIR=/mnt/appliance-backup
ENV_DIR=/etc/myarra
ENV_FILE=$ENV_DIR/appliance.env
KEY_FILE=/etc/koorsus-backup.key
CERT_DIR=/home/jeeves/myarra-certs
KOORSUS_BIN=/usr/local/sbin/koorsus
UNIT_DIR=/etc/systemd/system

log() { printf '%s %s\n' "$(date -Is)" "$*"; }
die() { log "FAIL  $*"; exit 1; }

log "MODE  ${MODE}"

# --- preconditions: refuse rather than limp ---------------------------
[ "$(id -u)" -eq 0 ] || die "must run as root"
[ -f /etc/nv_tegra_release ] || die "no /etc/nv_tegra_release: JetPack is not flashed"
log "OK    JetPack: $(head -1 /etc/nv_tegra_release)"

YEAR=$(date +%Y)
[ "$YEAR" -ge 2024 ] || die "clock reads $YEAR: set the time before installing"
log "OK    clock: $(date -Is)"

command -v python3 >/dev/null || die "python3 not found"
getent hosts pypi.org >/dev/null || die "no DNS: pip needs the network, run this on the bench"
log "OK    DNS resolves"

[ -f "$KOORSUS_APP/app.py" ] || die "$KOORSUS_APP does not look like the Koorsus repository"
log "OK    koorsus: $KOORSUS_APP"

if [ "$MODE" = "appliance" ]; then
  [ -f "$REPO/myarr_v2/app.py" ] || die "$REPO/myarr_v2/app.py not found"
  [ -f "$REPO/myarr_v2/myarra_settings.py" ] || die "$REPO/myarr_v2/myarra_settings.py not found"
  [ -f "$REPO/myarr_v2/requirements.txt" ] || die "$REPO/myarr_v2/requirements.txt not found"
  log "OK    myarra : $REPO"
  PAIRS="myarra koorsus"
else
  PAIRS="koorsus"
fi

for pair in $PAIRS; do
  [ -f "$CERT_DIR/${pair}-cert.pem" ] || die "missing $CERT_DIR/${pair}-cert.pem, see CERTIFICATES"
  [ -f "$CERT_DIR/${pair}-key.pem" ]  || die "missing $CERT_DIR/${pair}-key.pem, see CERTIFICATES"
done
log "OK    certificates present for: $PAIRS"

# --- directories ------------------------------------------------------
install -d -o "$SVC_USER" -g "$SVC_USER" -m 755 "$DATA_DIR"
install -d -o root -g root -m 700 "$BACKUP_DIR"
install -d -o root -g "$SVC_USER" -m 750 "$ENV_DIR"
log "OK    directories present: $DATA_DIR $BACKUP_DIR $ENV_DIR"

# --- python environment -----------------------------------------------
if [ ! -x "$VENV/bin/python" ]; then
  apt-get update -qq
  apt-get install -y -qq python3-venv python3-pip >/dev/null
  sudo -u "$SVC_USER" python3 -m venv "$VENV"
  log "OK    created venv $VENV"
else
  log "OK    venv already present"
fi

sudo -u "$SVC_USER" "$VENV/bin/pip" install -q -r "$KOORSUS_APP/requirements.txt"
log "OK    koorsus requirements installed"

if [ "$MODE" = "appliance" ]; then
  sudo -u "$SVC_USER" "$VENV/bin/pip" install -q -r "$REPO/myarr_v2/requirements.txt"
  log "OK    myarra requirements installed"
fi

# --- configuration: created once, never overwritten -------------------
if [ ! -f "$ENV_FILE" ]; then
  install -m 640 -o root -g "$SVC_USER" "$REPO/deploy/appliance.env.example" "$ENV_FILE"
  log "WARN  $ENV_FILE created from the template, fill in the blank values"
else
  log "OK    $ENV_FILE present, left untouched"
fi

# --- privileged scripts for the Koorsus side --------------------------
# Myarra needs none. Its backup is a systemd unit running as root, so it
# requires no sudoers entry. Koorsus admin pages call these through sudo.
normalise() {
  python3 - "$1" <<'PY'
import sys
p = sys.argv[1]
b = open(p, 'rb').read()
if b.startswith(b'\xef\xbb\xbf'):
    b = b[3:]
b = b.replace(b'\r\n', b'\n')
open(p, 'wb').write(b)
PY
}

install -d -o root -g root -m 755 "$KOORSUS_BIN"
for s in backup.sh verify-backup.sh restore-index.sh restore.sh reset.sh \
         smoke-check.sh setup-backup-key.sh export-usb.sh import-usb.sh \
         usb-eject.sh; do
  [ -f "$KOORSUS_APP/$s" ] || die "missing script $s in $KOORSUS_APP"
  install -o root -g root -m 755 "$KOORSUS_APP/$s" "$KOORSUS_BIN/$s"
  normalise "$KOORSUS_BIN/$s"
done
log "OK    koorsus scripts installed and normalised in $KOORSUS_BIN"

# --- backup passphrase: generated once, never regenerated -------------
if [ ! -f "$KEY_FILE" ]; then
  PASS=$(python3 -c "import secrets; print(secrets.token_hex(24))")
  umask 077
  printf '%s' "$PASS" > "$KEY_FILE"
  chown root:root "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  umask 022
  log "WARN  new backup passphrase generated. RECORD IT NOW:"
  printf '\n    %s\n\n' "$PASS"
  log "WARN  no copy of it exists anywhere else on this machine"
else
  log "OK    backup passphrase present, root only"
fi

# --- units ------------------------------------------------------------
UNITS="koorsus-app.service koorsus-llm.service appliance-backup.service appliance-backup.timer"
if [ "$MODE" = "appliance" ]; then
  UNITS="myarr.service myarra-bot.service $UNITS"
fi
for u in $UNITS; do
  [ -f "$REPO/deploy/$u" ] || die "missing unit template $REPO/deploy/$u"
  install -o root -g root -m 644 "$REPO/deploy/$u" "$UNIT_DIR/$u"
done
log "OK    units installed: $UNITS"

if [ -f "$UNIT_DIR/koorsus-app.service.d/env.conf" ]; then
  rm -f "$UNIT_DIR/koorsus-app.service.d/env.conf"
  rmdir "$UNIT_DIR/koorsus-app.service.d" 2>/dev/null || true
  log "OK    removed the superseded koorsus-app drop-in"
fi

# A Koorsus-only unit backs up only Koorsus.
if [ "$MODE" = "koorsus" ]; then
  install -d -m 755 "$UNIT_DIR/appliance-backup.service.d"
  printf '%s\n' '[Service]' \
    'Environment="APPLIANCE_MANIFEST=/home/jeeves/Client-Demo/deploy/backup/artifacts-koorsus.txt"' \
    > "$UNIT_DIR/appliance-backup.service.d/manifest.conf"
  log "OK    backup restricted to the Koorsus manifest"
fi

# --- USB automount, used by the Koorsus export and import scripts -----
cat > /etc/udev/rules.d/99-koorsus-usb.rules <<'UDEV'
ACTION=="add", SUBSYSTEM=="block", ENV{ID_FS_USAGE}=="filesystem", ENV{ID_BUS}=="usb", RUN+="/usr/bin/systemd-mount --no-block --collect /dev/%k /mnt/usb"
ACTION=="remove", SUBSYSTEM=="block", ENV{ID_FS_USAGE}=="filesystem", ENV{ID_BUS}=="usb", RUN+="/usr/bin/systemctl stop mnt-usb.mount"
UDEV
install -d -m 755 /mnt/usb
udevadm control --reload-rules
log "OK    USB automount rule installed"

# --- enable and start -------------------------------------------------
systemctl daemon-reload
systemctl enable koorsus-llm.service >/dev/null 2>&1 || true
systemctl start koorsus-llm.service
systemctl enable appliance-backup.timer >/dev/null 2>&1 || true
systemctl start appliance-backup.timer
log "OK    koorsus-llm and the backup timer are enabled"

START="koorsus-app.service"
if [ "$MODE" = "appliance" ]; then
  START="myarr.service myarra-bot.service koorsus-app.service"
fi
for u in $START; do
  systemctl enable "$u" >/dev/null 2>&1 || true
done

# Certificate-dependent services start last, deliberately.
systemctl restart $START
sleep 5

FAILED=0
for u in $START; do
  if systemctl is-active --quiet "$u"; then
    log "OK    $u active"
  else
    log "WARN  $u not active: journalctl -u $u -n 30"
    FAILED=1
  fi
done

# --- verification -----------------------------------------------------
PORTS="5003"
if [ "$MODE" = "appliance" ]; then
  PORTS="5002 5003"
fi
for p in $PORTS; do
  code=$(curl -sk -o /dev/null -w '%{http_code}' "https://127.0.0.1:${p}/" || echo 000)
  log "HTTP  ${p} -> ${code}"
done

# --- summary ----------------------------------------------------------
if [ "$FAILED" -eq 0 ]; then
  log "DONE  installation complete, mode $MODE"
else
  log "DONE  installation finished with a service down, see the WARN lines"
fi
log "      config     : $ENV_FILE"
log "      verify data: https://HOST:5002/setup/verify"
log "      first run  : $REPO/deploy/backup/backup.sh"
log "      passphrase : recorded nowhere except paper or your vault"
exit "$FAILED"
