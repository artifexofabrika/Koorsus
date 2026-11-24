# Provenance

What this directory is, where it came from, and what it is not.

## What it is

A snapshot of the Koorsus application that serves port 5003, taken on
2026-11-24 from `/home/jeeves/koorsus`, which is the `WorkingDirectory` of
`koorsus-app.service`.

## Why it exists

That directory is a git clone of **`github.com/artifexofabrika/Arkiv`** — a
different repository and a different product — sitting on commit `4550426`, with
uncommitted changes in the working tree. The Koorsus application therefore existed
in no history anywhere: the only copy of what it had become was the dirty tree on
the appliance, and a `git checkout` there would have reverted it toward Arkiv.

This directory is that history starting. It is a snapshot, not a fork with a
lineage: the differences between it and Arkiv at `4550426` are exactly the
uncommitted changes nobody had written down, captured here for the first time.

## What is deliberately not here

- `config.py` — holds credentials. Never committed. `config.example.py` is the
  template, and it is here.
- `incoming/`, `__pycache__/`, `*.pyc`, `*.db`, `*.sqlite3` — runtime.
- **The ten shell scripts.** They live in `deploy/koorsus-scripts/`, which is
  their single home and the source of truth for what is installed in
  `/usr/local/sbin/koorsus`. Duplicating them here would recreate the exact
  problem this cleanup removed: two copies, one of them stale, nothing saying
  which is which.

## What is Arkiv-named and stale

These came with the clone and were not deleted, because removing another
product's artefacts is a decision rather than a cleanup:

    ARKIV-ONE-PAGER.md
    SESSION-DELTA-2026-11-15-ARKIV.md
    99-arkiv-usb.rules
    arkiv-smoke.service, arkiv-smoke.timer
    systemd/            (arkiv-branded units for port 5001 that are not what runs)

`A43` records the `systemd/` directory. A full rename is a separate pass, and
until it happens these files are the reason a reader should not trust a filename
in this tree to describe what runs.

## Status: not yet the running copy

`koorsus-app.service` still starts from `/home/jeeves/koorsus`. Until that unit's
`WorkingDirectory` is re-pointed here and tested, the running application is the
clone and this directory is a snapshot of it. Two copies exist, deliberately and
temporarily, and this paragraph is the thing that says which is which.

The order that ends the duplication is recorded in `A54` and `A44`: this home
first, then a localhost credential path on `/ask`, because the two local callers
(the Myarra bot's SOP handler and the email agent) currently depend on an
unauthenticated endpoint; then repoint and test them; then stop, disable and mask
the legacy Koorsus on 5000 and archive it.
