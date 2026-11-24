# ESCROW

The backup passphrase, who holds it, and how to prove they can use it.
Answers A14. Written 2026-11-24, decisions taken by the owner that day.

## The problem, stated plainly

`/etc/koorsus-backup.key` encrypts every archive. It is 48 bytes, it is root-only,
and it is deliberately inside none of them: a key stored beside its own ciphertext
protects nothing. Every archive already on the disk, and every archive the 03:30
timer will write, is unreadable without it. Not degraded. Unreadable.

There is a second key file, `/etc/arkiv-backup.key` (27 bytes, 2026-11-15), and it
is a trap rather than a second passphrase to memorise. Both backup scripts default
to `/etc/koorsus-backup.key`: `deploy/backup/backup.sh` for the appliance archive
and `/usr/local/sbin/koorsus/backup.sh` for the Koorsus index archive. But
`/usr/local/sbin/koorsus/restore.sh` defaults to `/etc/arkiv-backup.key`, and no
unit or environment file sets `ARKIV_BACKUP_KEY`, so the restore path opens with a
key the archives were never written with. A restore run that way reports a bad
decrypt on a perfectly good archive, and the natural conclusion is that the backup
is corrupt (A53). Until that is fixed, set `ARKIV_BACKUP_KEY=/etc/koorsus-backup.key`
when restoring, or run `escrow-check.sh` first and let it tell you which passphrase
opens the file.

So the key's single point of failure is the appliance itself, and the appliance is
the thing the archives exist to survive. Until this document, escrow was not a
step anywhere: not in the installer, not in the install notes, not in the
handover. That is what this fixes.

## The model

Two copies, chosen for different failure modes rather than for redundancy.

1. **Two holders in the plant's password manager.** Convenient, survives one
   person leaving, fails if the account lapses or access is lost with the person.
2. **One printed copy, sealed, held off site.** Inconvenient, and the one that
   survives the account, the appliance and the company. This is the load-bearing
   copy.

They must not live together, and neither may live with the archives. A key in the
same bag as the USB stick is one loss, not two.

`setup-backup-key.sh` already tells the operator to store the passphrase in the
firm's password manager and to have at least two staff hold it. That advice is
correct and insufficient on its own, which is why the sealed copy exists.

## Printing and sealing it

Run as root, on the appliance, once per appliance:

    sudo cat /etc/koorsus-backup.key; echo

The file has no trailing newline, which is why the `echo` is there: without it the
next shell prompt runs into the passphrase. Write what appears on one line, by
hand or by print, and do not save it to a file on any machine on the way.

That is the passphrase that matters. `/etc/arkiv-backup.key` need only be sealed
as well if archives written before 2026-11-17 are kept somewhere, because it
predates the only Koorsus archive on this appliance; sealing it costs one more
envelope and settles the question for good.

Then seal it: envelope, flap sealed, signed across the seal, labelled with the
appliance name, the site, the date, and the words `BACKUP PASSPHRASE — SEALED`,
and stored off site. Record who holds it and where, in the same place the customer
records their other key material.

## Proving it, which is the whole point

An escrow copy nobody has tested is a hope with an envelope around it. Test it on
a machine that is not the appliance, from the paper copy, typing the passphrase
rather than pasting it:

    deploy/backup/escrow-check.sh /path/to/myarra-YYYYMMDD-HHMMSS.tar.gz.enc

It checks the archive's own `.sha256` first, so a damaged file is reported as
damaged rather than as a wrong passphrase; then it decrypts; then it insists the
result is a gzip tar containing `VERSIONS.txt`, and prints the versions written
inside. Exit 0 means the paper copy opens that archive. Exit 1 means the
passphrase or the file is wrong, and it says which. Exit 2 means it could not
start, and names what is missing.

Test the **oldest** archive you still hold as well as the newest, because a key
that has been rotated opens only the archives written since the rotation.

## What must never happen

- The passphrase on the appliance only. That is the defect this document exists
  for.
- The passphrase on the USB stick with the archives.
- The passphrase in this repository, in a ticket, in an email, or in a chat.
- `credential.helper store`, or any equivalent, holding anything on the appliance.
- Rotating the key without keeping the old one for as long as you keep the
  archives it encrypted. `setup-backup-key.sh` will overwrite the key on request
  and says nothing about the archives already written with it.

## If it is already lost

There is no recovery. The archives remain, and they are noise. Say so to the
customer in those words, and start again: a new key, a new archive, and this
document followed the first time. The only thing worse than losing the key is
discovering it during a restore.

## When this is re-checked

- At install, before the first production day. Not after.
- At every handover, by the person taking over, using the sealed copy.
- Annually, on the same calendar date, by whoever holds the sealed copy.

Each of those is a real check with a real archive, not a signature on a form.
