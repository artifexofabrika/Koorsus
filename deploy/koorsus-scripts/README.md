# Koorsus scripts

The bytes installed at `/usr/local/sbin/koorsus`, captured into version control on
2026-11-24 because until then they existed nowhere else.

## Why this directory exists

The live Koorsus application runs from `/home/jeeves/koorsus` (`koorsus-app.service`,
port 5003), and that directory is a clone of `github.com/artifexofabrika/Arkiv` —
a different repository and a different product, on a different commit from
`~/arkiv`. Five of the ten scripts here carried uncommitted edits renaming arkiv to
koorsus. A `git checkout` in that clone returns them to Arkiv paths, and the next
copy to `/usr/local/sbin` would have replaced the nightly backup with one writing
`arkiv-*.enc` into a directory Koorsus never reads, while the installed timer kept
reporting success. That is A54.

## The rule

This directory is the source of truth. Change here, commit here, then:

    sudo cp deploy/koorsus-scripts/<file> /usr/local/sbin/koorsus/<file>
    sudo chmod 755 /usr/local/sbin/koorsus/<file>

Do not edit the installed copies in place, and do not treat `~/koorsus` as the
source. It is another product's clone with local modifications.

## What is here, and what state each file is in

| file | state |
|---|---|
| `backup.sh` | renamed to koorsus paths. Writes `koorsus-*.tar.gz.enc` to `/mnt/koorsus-backup`, keeps 30. |
| `verify-backup.sh` | renamed. Decrypts the newest archive, checks sqlite integrity and the document count against live. |
| `restore-index.sh` | renamed. The working Koorsus index restore, and what the USB import runs. |
| `export-usb.sh` | renamed. Koorsus index only. The appliance-level export in `deploy/backup/` supersedes it and carries both products. |
| `import-usb.sh` | renamed. Copies the newest archive back and then `exec`s `restore-index.sh`, so it restores on insert. The appliance-level import deliberately does not, and is preferred. |
| `setup-backup-key.sh` | **corrected 2026-11-24.** Defaulted to `/etc/arkiv-backup.key` while both backups write with `/etc/koorsus-backup.key`. Now names the key the backups read, and warns that overwriting it orphans existing archives. |
| `restore.sh` | **replaced 2026-11-24 with a stub that refuses.** It was Arkiv's restore: wrong directory, wrong archive prefix, wrong key, wrong service. It cannot restore a Koorsus archive and reported a bad passphrase about good files. |
| `reset.sh` | **replaced 2026-11-24 with a stub that refuses.** It was Arkiv's factory reset and would empty the Arkiv library while leaving Koorsus untouched. There is no Koorsus reset yet (A17). |
| `usb-eject.sh` | generic, no product paths. |
| `smoke-check.sh` | belongs to Arkiv. It `cd`s to `/home/jeeves/arkiv` and writes `/var/log/arkiv-smoke.status`. The installed `arkiv-smoke.timer` runs `/usr/local/sbin/arkiv/smoke-check.sh`, not this copy, so this one is baggage from the clone. |

Two of these differ from what is installed right now: `restore.sh` and
`setup-backup-key.sh` were installed on 2026-11-24, and `reset.sh` has not been.
Install it before trusting this directory to match the machine.

## What is not here

The application. `koorsus-app.service` runs from `/home/jeeves/koorsus`, and that
source is still an uncommitted fork of the Arkiv repository. This directory covers
the scripts that back it up and restore it; it does not contain what they protect.
Moving the application into a repository of its own, and re-pointing the unit, is
recorded as A54 and needs a test window rather than a demo week.
