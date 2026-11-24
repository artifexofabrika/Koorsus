# ARKIV - INSTALLATION

One command on a flashed Jetson. The script is idempotent: running it on a
provisioned board changes nothing and breaks nothing.

## PREREQUISITES (not scriptable)

- Jetson Orin Nano 8GB, NVMe fitted.
- JetPack flashed via SDK Manager and first boot completed.
- A user with sudo. The installer creates `jeeves` if absent.
- Working network and DNS. apt and pip both need it.
- The repository at /home/jeeves/arkiv.
- A TLS certificate. Without one the installer stops before enabling the
  service, deliberately.

## THE COMMAND

    cd /home/jeeves/arkiv
    sudo bash install.sh

## WHAT IT DOES

1. Verifies JetPack, clock, DNS, user and repository. Refuses on any failure.
2. Creates /mnt/lake and /mnt/arkiv-backup.
3. Creates the venv if absent and installs requirements.txt.
4. Creates config.py from the example if absent, and never overwrites one.
5. Installs the privileged scripts to /usr/local/sbin/arkiv, root-owned,
   stripping any BOM or carriage returns on the way in.
6. Writes /etc/sudoers.d/arkiv, the pinned privilege list, and validates it
   with visudo before proceeding.
7. Installs the USB automount udev rule.
8. Generates the backup passphrase if absent and prints it once.
9. Installs systemd units and the service drop-in, then enables and starts.
10. Prints the next steps.

## CERTIFICATE

The installer expects /home/jeeves/myarra-certs/arkiv-cert.pem and
arkiv-key.pem. To create them:

    cd /home/jeeves/myarra-certs
    mkcert -cert-file arkiv-cert.pem -key-file arkiv-key.pem \
           arkiv.local localhost 192.168.100.2

The mkcert root CA must be trusted on any Windows machine that will browse
to the appliance, or the browser will warn. For a customer unit, decide
whether to ship the mkcert CA or use a proper internal CA; that is a
provisioning decision, not a script one.

The drop-in /etc/systemd/system/arkiv.service.d/workers.conf is the
authority for worker count and certificate paths. The base unit still names
two workers; the drop-in overrides it to one. Do not remove the empty
ExecStart= line or systemd will run both.

## AFTER INSTALLING

1. Edit config.py: set SECRET_KEY and the office PIN. Both are required.
2. Create the first account:

       /home/jeeves/jeeves-env/bin/python users.py add "Name" "long-pin" admin

   Until an account exists the appliance accepts the shared PIN from
   config.py with any username, so do not delay this.
3. Ingest documents at https://HOST:5001/ingest, one matter tag per file set.
4. Record the backup passphrase printed during install. It is not
   recoverable and no copy exists anywhere else on the machine.

## UPDATING AN EXISTING UNIT

    cd /home/jeeves/arkiv && git pull
    sudo bash install.sh
    python3 smoke.py

The installer will not touch config.py, will not regenerate an existing
passphrase, and will not delete data.

## VOLUME PRODUCTION

Do not flash and provision each unit. Provision one, verify it, then clone
its NVMe with dd or partclone and write that image to the rest. Three hours
becomes twenty minutes. The installer then serves the development board and
software updates.

## TROUBLESHOOTING

- "no /etc/nv_tegra_release": JetPack is not flashed.
- "clock reads 1969": no RTC battery; set the time before installing, or TLS
  and logs will be wrong.
- "service not active": sudo journalctl -u arkiv -n 40
- A script fails with "not found" though it exists: BOM or CRLF in the
  shebang. The installer normalises on install; if you edited one in place,
  run it through python3 -c to strip both.
- Backups failing: check /var/log/arkiv-backup.log and that the passphrase
  file is root:root 600.
- A button reports "sudo: a password is required": the pinned rule is
  missing. Compare sudo -n -l with /etc/sudoers.d/arkiv and run visudo -c.

## RESETTING TO A CLEAN LIBRARY

Admin page, Reset Library. The index is moved aside, never deleted. Restore
it, or restore from the newest backup.
