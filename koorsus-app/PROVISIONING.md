# Arkiv Provisioning Runbook

Internal document. For Randy Wolf and any authorised manufacturing partner.
Not customer-facing. The customer receives the Quick Start card, not this.

Target: one hour from bare Jetson to sealed box, repeatable.

## 1. Hardware

Per unit:

- NVIDIA Jetson Orin Nano 8GB Developer Kit (primary stock)
- 256GB NVMe SSD (or larger; 256GB is enough for the base tier)
- USB-C to Gigabit Ethernet adapter (the internal Realtek Wi-Fi on the
  Jetson is defective on multiple boards; use wired Ethernet through the
  adapter)
- Aluminum enclosure with power button and ventilation
- 12V 3A power supply (Jetson stock)
- Cat 5e or Cat 6 Ethernet cable, 1.5m
- USB flash drive for the customer's backup (16GB, one per unit)
- Printed Quick Start card (laminated)
- Printed PIN card, in a sealed envelope
- Return shipping label for the device swap program

For the field, keep one spare unit per ten deployed. Spares are identical
to shipped units, ready to go.

## 2. Operating system with full-disk encryption

This is the step that gives the customer encrypted at rest. It must be
done on the bare device before any Arkiv software is installed.

Note: this procedure has been planned but not yet executed end to end on
a bare Jetson at the time of this document. Validate it on the first
provisioning run and correct any drift before shipping.

### 2.1. Prepare the flash

On a Linux or Windows machine with USB access:

1. Download NVIDIA JetPack 6.x (L4T 36.x) SDK Manager.
2. Select the Orin Nano 8GB target.
3. In the "Flash" step, choose "Manual" and select "Full disk encryption."
4. SDK Manager will ask for the disk encryption passphrase. Do not use
   the customer's passphrase here. Use a provisioning passphrase
   (16+ characters, random) that is stored in the manufacturer's vault
   and known only to the person provisioning. The customer's passphrase
   will be set on first boot.
5. Complete the flash. The device reboots once and asks for the disk
   passphrase at the LUKS unlock prompt.

### 2.2. First boot

1. Enter the provisioning passphrase at the LUKS unlock prompt.
2. The device boots to the Ubuntu first-run setup.
3. Create the user `jeeves` with a strong temporary password. This user
   will run the services.
4. Set the hostname to `koorsus` (or the customer-specific name agreed at
   order).
5. Complete the setup and reboot.

## 3. Base system

On the device, as user `jeeves`:

    sudo apt update && sudo apt upgrade -y
    sudo apt install -y python3 python3-pip python3-venv git curl openssl \
                        sqlite3 ca-certificates mkcert

Install the Python environment:

    python3 -m venv ~/jeeves-env
    source ~/jeeves-env/bin/activate
    pip install --upgrade pip

SSH key auth (from the provisioning workstation):

    ssh-copy-id jeeves@<device-ip>

Network: static IP or DHCP reservation, on the customer's network segment.

## 4. LLM

The Arkiv retrieval layer needs a local LLM. We use Qwen 2.5 3B served by
llama.cpp on port 8080.

    cd ~
    git clone https://github.com/ggerganov/llama.cpp
    cd llama.cpp
    make LLAMA_CUDA=1

Download the model to `~/llama.cpp/models/qwen2.5-3b/`:

    qwen2.5-3b-instruct-q4_k_m.gguf

Create `/etc/systemd/system/koorsus-llm.service`:

    [Unit]
    Description=Koorsus LLM server
    After=network.target

    [Service]
    User=jeeves
    Group=jeeves
    WorkingDirectory=/home/jeeves/llama.cpp
    ExecStart=/home/jeeves/llama.cpp/llama-server \
        -m /home/jeeves/llama.cpp/models/qwen2.5-3b/qwen2.5-3b-instruct-q4_k_m.gguf \
        --host 127.0.0.1 --port 8080 -c 4096 -t 4
    Restart=on-failure
    RestartSec=5

    [Install]
    WantedBy=multi-user.target

Enable:

    sudo systemctl daemon-reload
    sudo systemctl enable --now koorsus-llm.service

Verify:

    curl -s http://127.0.0.1:8080/v1/models | head -c 200

## 5. Arkiv

    cd ~
    git clone https://github.com/artifexofabrika/arkiv.git

    cd arkiv
    source ~/jeeves-env/bin/activate
    pip install flask werkzeug chromadb sentence-transformers \
                transformers pypdf python-docx odfpy gunicorn

Copy the config template and edit it:

    cp config.example.py config.py
    nano config.py

In config.py, set:

- `SECRET_KEY` to a random 64-character hex string. Generate with:
  `python3 -c "import secrets; print(secrets.token_hex(32))"`
- `ARKIV_PIN` to the customer's 16-character PIN, agreed at order.

Set up the backup passphrase (customer's choice, 16+ characters):

    sudo ~/arkiv/setup-backup-key.sh

Install the systemd units:

    sudo cp ~/arkiv/arkiv.service /etc/systemd/system/arkiv.service
    sudo cp ~/arkiv/arkiv-backup.service /etc/systemd/system/arkiv-backup.service
    sudo cp ~/arkiv/arkiv-backup.timer /etc/systemd/system/arkiv-backup.timer
    sudo systemctl daemon-reload

The three unit files are in the repository under `systemd/`.

## 6. TLS

The device needs a certificate that the customer's browsers will trust
without warnings. We use mkcert with the customer's device hostname and IP.

    mkcert -install
    mkdir -p ~/myarra-certs
    cd ~/myarra-certs
    mkcert -cert-file myarra-cert.pem -key-file myarra-key.pem \
        koorsus localhost 127.0.0.1 <customer-ip>

Distribute the root CA to the customer:

    ls ~/.local/share/mkcert/rootCA.pem

Copy the rootCA.pem to a USB, hand it to the customer's IT person, and
give them the one-paragraph instruction:

    "Install this certificate as a Trusted Root Certification Authority
    on each computer that will access the Arkiv appliance. On Windows,
    double-click the file, choose 'Install Certificate', select 'Local
    Machine', 'Place all certificates in the following store', 'Trusted
    Root Certification Authorities', finish. On macOS, open Keychain
    Access, drag the file to the System keychain, and mark it as Always
    Trust."

This is the one manual step the customer performs. It is worth a phone
call with their IT person to walk through.

## 7. Start services

    sudo systemctl enable --now koorsus-llm.service
    sudo systemctl enable --now arkiv.service
    sudo systemctl enable --now arkiv-backup.timer

Check:

    systemctl is-active koorsus-llm arkiv
    systemctl list-timers arkiv-backup.timer
    sudo ss -tlnp | grep 5001

Expected: LLM active, Arkiv active, timer scheduled for 03:00, port 5001
listening.

## 8. Smoke test

Before sealing the box, all five checks must pass.

1. HTTPS reachable and login page renders:

       curl -sk -o /dev/null -w "%{http_code}\n" https://127.0.0.1:5001/login

   Expected: 200.

2. Login works:

       curl -sk -c /tmp/cj -X POST https://127.0.0.1:5001/login \
            -d "pin=<customer-pin>" -o /dev/null
       curl -sk -b /tmp/cj https://127.0.0.1:5001/matters

   Expected: `{"matters":[]}` (empty library on a fresh device).

3. Ingest one test document (a short .txt), verify it appears:

       curl -sk -b /tmp/cj -F "files=@test.txt" -F "uploader=provision" \
            -F "tag=SMOKE-TEST" https://127.0.0.1:5001/upload -o /dev/null
       curl -sk -b /tmp/cj https://127.0.0.1:5001/matters

   Expected: one matter, `SMOKE-TEST`, with one or more chunks.

4. Query the test document:

       curl -sk -b /tmp/cj -X POST https://127.0.0.1:5001/ask \
            -H "Content-Type: application/json" \
            -d '{"question":"What is in the smoke test?","matter":"SMOKE-TEST"}'

   Expected: an answer with sources listed, no 500 error.

5. Backup runs and the archive verifies:

       sudo /home/jeeves/arkiv/backup.sh
       ls -la /mnt/arkiv-backup/
       sudo /home/jeeves/arkiv/verify-backup.sh (when implemented)

   Expected: one `.tar.gz.enc` and one `.sha256`.

After passing all five, remove the smoke test document:

    sudo systemctl stop arkiv
    rm -rf /mnt/lake/arkiv_index
    sudo systemctl start arkiv

Or run `reset.sh` (when implemented) to leave the device in factory state.

## 9. Packaging

What goes in the box:

- The appliance, in its enclosure, with the NVMe secured
- Power adapter and cable
- Ethernet cable (1.5m)
- The backup USB drive, formatted, empty, labelled with the customer's
  firm name
- The Quick Start card, laminated
- The PIN card, in a sealed envelope, containing:
    - The customer's 16-character login PIN
    - The customer's backup encryption passphrase
    - The appliance serial number
    - The appliance URL (e.g., https://arkiv.<firm>.local:5001 or the
      static IP assigned)
- The return shipping label, folded and placed under the Quick Start card
- A single sheet of paper: "Your Arkiv was provisioned on <date> by
  <name>. Contact <phone> with any questions."

Do not include the PROVISIONING.md document. Do not include any
credentials other than the PIN card.

## 10. Troubleshooting during provisioning

The common failures, in the order we have actually seen them:

**Device does not boot after flashing.**
  The LUKS passphrase was typed wrong at first boot. Reboot and try
  again. If it fails three times, the device will halt. Power cycle and
  re-enter the provisioning passphrase from the vault.

**Arkiv service fails to start.**
  Check `sudo journalctl -u arkiv -n 40`. The usual cause is a missing
  dependency in the venv, or the cert file paths in the systemd unit are
  wrong. Confirm `/home/jeeves/myarra-certs/myarra-cert.pem` exists.

**Browser shows "Not secure."**
  The customer's browser does not trust the mkcert root CA. The
  distribution step (section 6) was missed, or the IT person installed
  the root CA in the wrong store.

**`/matters` returns 500.**
  The ChromaDB directory does not exist or is not writable by `jeeves`.
  Check `ls -la /mnt/lake/arkiv_index`.

**LLM does not respond on port 8080.**
  The model file is missing or the path in `koorsus-llm.service` is
  wrong. Check `sudo journalctl -u koorsus-llm -n 40`.

**Backup timer does not fire.**
  The timer is scheduled for 03:00 local. During provisioning, the system
  clock may not be set. Verify with `timedatectl` and correct if needed.

## 11. Handoff to customer

When you deliver the appliance:

1. Hand the box to the customer's office manager.
2. Walk them through the Quick Start card once, in person, ten minutes.
3. Confirm the PIN card is in their hand and the sealed envelope is
   unbroken.
4. Have them sign the delivery receipt with the serial number.
5. Tell them: "If the appliance fails, call us before noon Eastern. We
   will ship a replacement the same day or next business day. Keep the
   backup USB in your safe."

That is the whole handoff. Twenty minutes if they are prepared, forty if
they ask questions. Do not leave the appliance without the ten-minute
walk-through. The PIN card is what makes the difference between a tool
they use and a box they forget.

## Status

Last updated 2026-11-15.

Tested: base system, LLM, Arkiv install, services, TLS, smoke test,
backup, restore.

Planned but not executed end to end on a bare Jetson: LUKS full-disk
encryption (section 2). This is the single gap between the current
development state and a shippable unit. Run it on the first bare device
and correct any drift in this document.
