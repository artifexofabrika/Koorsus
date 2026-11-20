# MYARRA APPLIANCE INSTALLATION

Hand-built, one board at a time. There is no standard image: a board is
flashed with JetPack, then provisioned by hand with one script.

Proven state, 2026-11-19: the installer has been run twice in Koorsus-only
mode on the reference board, EXIT=0 both times. Appliance mode has been
reviewed but never executed.

Two ways to provision a unit:

    A. Run this procedure on the board. Needs network. Minutes per board.
    B. Provision one board, verify it, then clone its NVMe. Use this for
       volume. A plant with no route to the internet cannot run step 5.

## 1. What you are installing

The product is four services.

    myarr          5002   Myarra, the production tracker
    myarra-bot            Myarra Telegram capture
    koorsus-app    5003   Koorsus, the document assistant
    koorsus-llm    8080   llama.cpp serving the model

Two services must NOT be installed: arkiv.service, a separate product, and
the old koorsus.service on port 5000, which exists on the development
board only because a Telegram bot posts to it.

Koorsus may be sold alone. Myarra is never sold without Koorsus. The
installer takes --koorsus for the first case.

## 2. Hardware and preconditions

    Jetson Orin Nano 8GB with NVMe fitted
    JetPack 6.2 or later, flashed with SDK Manager, first boot completed
    A user with sudo. The installer creates jeeves if absent.
    Network with DNS and a route to PyPI, on the bench only
    A USB stick carrying the model file and the certificates

The installer refuses to run if JetPack is absent, if the clock reads
before 2024, if DNS fails, or if a certificate is missing. It refuses
rather than proceeding, deliberately.

## 3. Clock

The board has no RTC battery. If the clock reads 1969, set it before
installing, or TLS and logs will both be wrong.

    sudo date -s "2026-11-20 04:00:00"

## 4. The code

Myarra comes from github.com/artifexofabrika/Koorsus into
/home/jeeves/Client-Demo. Koorsus is the Arkiv codebase deployed a second
time, into /home/jeeves/koorsus. They are separate working copies of
separate repositories. Neither is a branch of the other.

    git clone <url> /home/jeeves/Client-Demo
    git clone <url> /home/jeeves/koorsus

Every backup writes both commit hashes into the archive as VERSIONS.txt,
so a restored appliance knows which code its data belongs to.

## 5. Python

One virtual environment serves both products, at /home/jeeves/jeeves-env.
The installer creates it if absent and installs two requirements files.

    koorsus/requirements.txt    range-pinned, includes the CUDA and
                                embedding stack
    myarr_v2/requirements.txt   exactly pinned: Flask, gunicorn,
                                requests, waitress

torch is deliberately absent from the Koorsus list. On a Jetson it comes
from the platform image. Installing it from PyPI replaces the platform
build and sentence-transformers silently falls back to CPU.

## 6. Certificates

Two pairs, generated with mkcert into /home/jeeves/myarra-certs. The
installer does not generate them and will refuse to start a
certificate-dependent service without them.

    cd /home/jeeves/myarra-certs
    mkcert -cert-file myarra-cert.pem  -key-file myarra-key.pem  localhost 192.168.100.2 koorsus
    mkcert -cert-file koorsus-cert.pem -key-file koorsus-key.pem localhost 192.168.100.2 koorsus

The SAN list must include the address a tablet will actually use, or the
floor display cannot be installed as an app. Replace 192.168.100.2 with the
unit's address first.

The mkcert root CA must be trusted on every tablet and Windows machine that
browses to the appliance, or the browser warns and the PWA will not install.

## 7. Backup passphrase, and where it goes

Every archive is encrypted with one passphrase. The installer generates it
once and prints it once. It is stored nowhere else on the machine.

    /etc/koorsus-backup.key    root:root, 0600

WRITE IT ON PAPER and keep it off the appliance. If it is lost, every
archive becomes unreadable noise, permanently. There is no recovery path.

## 8. Configuration

One env file, read by all four units.

    sudo install -d -o root -g jeeves -m 750 /etc/myarra
    sudo install -m 640 -o root -g jeeves \
         /home/jeeves/Client-Demo/deploy/appliance.env.example \
         /etc/myarra/appliance.env
    sudo nano /etc/myarra/appliance.env

Values left commented out fall back to the built-in default in code. The
seven that matter:

    MYARRA_DB         where the production database lives
    LLM_URL           must match --port in koorsus-llm.service, which is 8080
    MYARRA_TLS_CERT   certificate for the tracker on 5002
    MYARRA_TLS_KEY
    KOORSUS_TLS_CERT  certificate for the document assistant on 5003
    KOORSUS_TLS_KEY
    KOORSUS_MODEL     model file; Nano 3B, NX 7B or 14B

The installer creates this file if absent and never overwrites it. If a new
variable is added to a unit template, add it here too: systemd resolves an
undefined variable to an empty string, so the failure appears as a bad
argument rather than as a missing variable.

## 9. Install

    sudo bash /home/jeeves/Client-Demo/deploy/install.sh            # both
    sudo bash /home/jeeves/Client-Demo/deploy/install.sh --koorsus # documents only

It is idempotent. Running it on a provisioned board changes nothing and
breaks nothing, verified by running it twice on the reference board.

Order of work: preconditions; directories; virtual environment and
requirements; appliance.env if absent; Koorsus scripts into
/usr/local/sbin/koorsus, normalised for BOM and CRLF; the backup passphrase
if absent; units; USB automount rule; enable and start; verification.

Certificate-dependent services start last and are checked afterwards. A
service that fails to come up is reported rather than assumed away.

## 10. Verification

    systemctl is-active myarr myarra-bot koorsus-app koorsus-llm

All four must read active. Then the pages:

    for u in / /reconciliation /changeover /pdca /pdca/log /setup /setup/verify /herbie /floor /ask; do
      printf "%-18s " "$u"
      curl -sk -o /dev/null -w "%{http_code}\n" "https://127.0.0.1:5002$u"
    done

Ten lines, all reading 200. Then /floor from a tablet on the network, on the
trusted certificate, installed to the home screen.

/setup/verify shows the data warnings and the LLM reachability check
together. A failure line there is serious: with the LLM unreachable, ask.py
shows errors and the bot answers "I did not understand" as though the
operator had mumbled. That looks like a bad bot install and is actually a
bad LLM_URL.

## 11. Backup, and a rehearsal

The timer is installed and enabled by the installer. It runs at 03:30 daily
and verifies the archive it has just written, in the same run.

First archive and its proof:

    sudo /home/jeeves/Client-Demo/deploy/backup/backup.sh
    sudo /home/jeeves/Client-Demo/deploy/backup/verify.sh

Exit 0 from both. The verify output must include a content line such as
"406 jobs, 1659 hours, 13 line events". Integrity checks alone do not prove
an archive is not empty.

Then rehearse a restore into a scratch tree. This touches nothing live:

    sudo rm -rf /tmp/restore-test
    sudo env APPLIANCE_RESTORE_ROOT=/tmp/restore-test \
         /home/jeeves/Client-Demo/deploy/backup/restore.sh

Compare restored against live by content, not by eye:

    for f in /mnt/lake/myarra.db /tmp/restore-test/mnt/lake/myarra.db; do
      printf "%-42s " "$f"; sqlite3 "$f" .dump | sha256sum
    done

The two hashes must match.

Offsite copy: /mnt/appliance-backup is on the same filesystem as the data,
so it protects against deletion and corruption but not against the disk
dying. The USB export and import scripts in /usr/local/sbin/koorsus are
hardcoded to /mnt/koorsus-backup and do not carry the appliance archive.
Until that changes, copy the newest myarra archive to the stick by hand
after each install.

## 12. Customer handover

    users      https://HOST:5002/admin       add the line leads
    master     https://HOST:5002/setup       CSV templates and upload
    verify     https://HOST:5002/setup/verify
    floor      https://HOST:5002/floor       install on the tablet
    documents  https://HOST:5003             ingest the customer's files

Before ingesting a single document, reset the Koorsus library from its admin
page. The reference board carries test chunks from files that no longer
exist, and a customer unit must not ship with them.

There is no document root yet. Koorsus stores extracted text and metadata
and never the original file, so the customer's document store is theirs to
back up separately. This is an open design decision, not a shipped feature.

## 13. Rollback

Every restore keeps what it replaced under
/mnt/appliance-backup/pre-restore-<timestamp>/. To return to the state before
the last restore, copy those files back into place and restart the services.

To remove the units without touching any data:

    sudo systemctl disable --now myarr myarra-bot koorsus-app appliance-backup.timer
    sudo rm -f /etc/systemd/system/myarr.service /etc/systemd/system/myarra-bot.service
    sudo rm -f /etc/systemd/system/koorsus-app.service /etc/systemd/system/koorsus-llm.service
    sudo rm -f /etc/systemd/system/appliance-backup.service /etc/systemd/system/appliance-backup.timer
    sudo systemctl daemon-reload

The database, the index, the certificates and the env file all stay.

## Appendix: the whole thing at a glance

     1  flash JetPack with SDK Manager, complete first boot
     2  check the clock, set it if it reads 1969
     3  clone both repositories
     4  generate both certificate pairs with mkcert
     5  trust the mkcert CA on every tablet and Windows machine
     6  write /etc/myarra/appliance.env
     7  run deploy/install.sh
     8  four services active
     9  ten routes return 200
    10  backup, verify, and rehearse a restore into /tmp
    11  WRITE THE PASSPHRASE ON PAPER
    12  reset the Koorsus library
    13  add users and import CSV master data
    14  install the floor display on a tablet
    15  hand over
