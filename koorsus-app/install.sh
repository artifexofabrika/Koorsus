#!/usr/bin/env bash
# Arkiv appliance installer. Idempotent: safe to run on a provisioned board.
set -euo pipefail

APP_DIR=/home/jeeves/arkiv
SVC_USER=jeeves
BIN_DIR=/usr/local/sbin/arkiv
DATA_DIR=/mnt/lake
BACKUP_DIR=/mnt/arkiv-backup
KEY_FILE=/etc/arkiv-backup.key

log() { printf '%s %s\n' "$(date -Is)" "$*"; }
die() { log "FAIL  $*"; exit 1; }

[ "$(id -u)" -eq 0 ] || die "must run as root"
[ -d "$APP_DIR" ] || die "$APP_DIR not found - copy the repository there first"
[ -f "$APP_DIR/app.py" ] || die "$APP_DIR does not look like the Arkiv repository"
command -v python3 >/dev/null || die "python3 not found"

log "OK    preconditions satisfied"
log "      app      : $APP_DIR"
log "      service  : $SVC_USER"
log "      data     : $DATA_DIR"
log "      backups  : $BACKUP_DIR"

# --- board and environment ---------------------------------------------
[ -f /etc/nv_tegra_release ] || die "no /etc/nv_tegra_release: JetPack is not flashed"
log "OK    JetPack: $(head -1 /etc/nv_tegra_release)"

YEAR=$(date +%Y)
[ "$YEAR" -ge 2024 ] || die "clock reads $YEAR: set the time before installing"
log "OK    clock: $(date -Is)"

getent hosts github.com >/dev/null || die "no DNS: network is required for apt and pip"
log "OK    DNS resolves"

if ! id "$SVC_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$SVC_USER"
  log "OK    created service user $SVC_USER (set a password with: passwd $SVC_USER)"
fi
log "OK    service user: $SVC_USER"

# --- filesystem and python ---------------------------------------------
install -d -o "$SVC_USER" -g "$SVC_USER" -m 755 "$DATA_DIR"
install -d -o "$SVC_USER" -g "$SVC_USER" -m 700 "$BACKUP_DIR"
log "OK    data and backup directories present"

VENV=/home/jeeves/jeeves-env
if [ ! -x "$VENV/bin/python" ]; then
  apt-get update -qq
  apt-get install -y -qq python3-venv python3-pip >/dev/null
  sudo -u "$SVC_USER" python3 -m venv "$VENV"
  log "OK    created venv at $VENV"
else
  log "OK    venv already present"
fi

[ -f "$APP_DIR/requirements.txt" ] || die "requirements.txt missing"
sudo -u "$SVC_USER" "$VENV/bin/pip" install -q -r "$APP_DIR/requirements.txt"
log "OK    python requirements installed"

if [ ! -f "$APP_DIR/config.py" ]; then
  cp "$APP_DIR/config.example.py" "$APP_DIR/config.py"
  chown "$SVC_USER":"$SVC_USER" "$APP_DIR/config.py"
  chmod 600 "$APP_DIR/config.py"
  log "WARN  config.py created from the example: set SECRET_KEY and PIN"
fi
log "OK    config present"

# --- privileged scripts --------------------------------------------------
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

install -d -o root -g root -m 755 "$BIN_DIR"
for s in backup.sh verify-backup.sh restore-index.sh reset.sh \
         export-usb.sh import-usb.sh usb-eject.sh; do
  [ -f "$APP_DIR/$s" ] || die "missing script $s in $APP_DIR"
  install -o root -g root -m 755 "$APP_DIR/$s" "$BIN_DIR/$s"
  normalise "$BIN_DIR/$s"
done
log "OK    scripts installed and normalised in $BIN_DIR"

cat > /etc/sudoers.d/arkiv <<'SUDO'
Cmnd_Alias ARKIV_BACKUP  = /usr/local/sbin/arkiv/backup.sh
Cmnd_Alias ARKIV_VERIFY  = /usr/local/sbin/arkiv/verify-backup.sh
Cmnd_Alias ARKIV_INDEX   = /usr/local/sbin/arkiv/restore-index.sh
Cmnd_Alias ARKIV_EXPORT  = /usr/local/sbin/arkiv/export-usb.sh
Cmnd_Alias ARKIV_IMPORT  = /usr/local/sbin/arkiv/import-usb.sh
Cmnd_Alias ARKIV_EJECT   = /usr/local/sbin/arkiv/usb-eject.sh
Cmnd_Alias ARKIV_CHOWN   = /usr/bin/chown jeeves\:jeeves /mnt/lake/arkiv_index, /usr/bin/chown -R jeeves\:jeeves /mnt/lake/arkiv_index
Cmnd_Alias ARKIV_RESTART = /usr/bin/systemctl restart arkiv

jeeves ALL=(root) NOPASSWD: ARKIV_BACKUP, ARKIV_VERIFY, ARKIV_INDEX, ARKIV_EXPORT, ARKIV_IMPORT, ARKIV_EJECT, ARKIV_CHOWN, ARKIV_RESTART
SUDO
chmod 440 /etc/sudoers.d/arkiv
visudo -c >/dev/null || die "sudoers validation failed"
log "OK    sudoers policy written and validated"

cat > /etc/udev/rules.d/99-arkiv-usb.rules <<'UDEV'
ACTION=="add", SUBSYSTEM=="block", ENV{ID_FS_USAGE}=="filesystem", ENV{ID_BUS}=="usb", RUN+="/usr/bin/systemd-mount --no-block --collect /dev/%k /mnt/usb"
ACTION=="remove", SUBSYSTEM=="block", ENV{ID_FS_USAGE}=="filesystem", ENV{ID_BUS}=="usb", RUN+="/usr/bin/systemctl stop mnt-usb.mount"
UDEV
install -d -m 755 /mnt/usb
udevadm control --reload-rules
log "OK    USB automount rule installed"

# --- backup passphrase ---------------------------------------------------
if [ ! -f "$KEY_FILE" ]; then
  PASS=$(python3 -c "import secrets; print(secrets.token_hex(24))")
  umask 077
  printf '%s' "$PASS" > "$KEY_FILE"
  chown root:root "$KEY_FILE"
  chmod 600 "$KEY_FILE"
  umask 022
  log "WARN  new backup passphrase generated. RECORD IT NOW:"
  printf '\n    %s\n\n' "$PASS"
  log "WARN  without it the archives cannot be recovered. It is not stored elsewhere."
else
  log "OK    backup passphrase present (root-only)"
fi

# --- systemd -------------------------------------------------------------
for u in "$APP_DIR"/systemd/*.service "$APP_DIR"/systemd/*.timer; do
  [ -f "$u" ] || continue
  install -o root -g root -m 644 "$u" /etc/systemd/system/ || true
done
for u in arkiv-smoke.service arkiv-smoke.timer; do
  [ -f "$APP_DIR/$u" ] && install -o root -g root -m 644 "$APP_DIR/$u" /etc/systemd/system/
done
systemctl daemon-reload
log "OK    systemd units installed"

# --- certificate and service ---------------------------------------------
CERT_DIR=/home/jeeves/myarra-certs
CERT=$CERT_DIR/arkiv-cert.pem
CERTKEY=$CERT_DIR/arkiv-key.pem
SKIP_SERVICE=1

if [ ! -f "$CERT" ] || [ ! -f "$CERTKEY" ]; then
  log "WARN  no certificate at $CERT"
  log "WARN  generate one, then run this installer again:"
  log "      mkcert -cert-file $CERT -key-file $CERTKEY arkiv.local localhost"
else
  install -d -m 755 /etc/systemd/system/arkiv.service.d
  cat > /etc/systemd/system/arkiv.service.d/workers.conf <<'UNIT'
[Service]
ExecStart=
ExecStart=/home/jeeves/jeeves-env/bin/gunicorn \
    --bind 0.0.0.0:5001 \
    --workers 1 \
    --timeout 180 \
    --access-logfile - \
    --error-logfile - \
    --certfile @CERT@ \
    --keyfile @KEY@ \
    app:app
UNIT
  sed -i "s|@CERT@|$CERT|g; s|@KEY@|$CERTKEY|g" /etc/systemd/system/arkiv.service.d/workers.conf
  systemctl daemon-reload
  SKIP_SERVICE=0
  log "OK    service drop-in written"
fi

if [ "$SKIP_SERVICE" -eq 0 ]; then
  systemctl enable arkiv.service arkiv-backup.timer arkiv-verify.timer arkiv-smoke.timer >/dev/null 2>&1 || true
  systemctl restart arkiv.service
  sleep 3
  if systemctl is-active --quiet arkiv; then
    log "OK    arkiv.service active"
  else
    log "WARN  arkiv.service not active: journalctl -u arkiv -n 30"
  fi
else
  log "WARN  service not enabled until a certificate exists"
fi

# --- summary --------------------------------------------------------------
log "DONE  installation complete"
log "      edit $APP_DIR/config.py to set SECRET_KEY and the office PIN"
log "      create a user: $VENV/bin/python $APP_DIR/users.py add Name PIN admin"
log "      ingest documents at https://HOST:5001/ingest"
