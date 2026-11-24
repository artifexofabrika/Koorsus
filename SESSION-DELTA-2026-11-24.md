# SESSION DELTA 2026-11-24 — THE QUEUE CLOSED

Follows SESSION-DELTA-2026-11-23.md. HEAD before this document's own commit:
912c68b. Everything below was verified on the reference Jetson.

Read in this order: PHILOSOPHY.md, deploy/STATE.md, deploy/AUDIT.md, then this.

## What was true when it began

The previous delta said HEAD was fd670a5, which was stale by two commits, and that
the tracer "already detects a narrative containing a number the payload does not
carry, and only warns", which was false: nothing in the product traced anything and
the only tracer was a print in a test tool comparing against the stats dictionary
rather than the prompt.

The queue was four items: A01's Telegram half, the tracer veto, A14 and A16, and a
human on the glass. Three are done. The fourth is the only one left, and it cannot
be done by an instance.

## Shipped

    a709d1b  A01's bot half. ideal_rate() returns None, five call sites handled.
    17e3c01  Audit: A01 closed, A50 recorded.
    aae0467  A50. The view keeps rows a missing rate used to delete; the card says
             unknown instead of zero. 16 checks.
    e61eae7  The tracer veto, traced against the whole prompt. 18 checks.
    16a1e67  Records: the delta's two false statements, A51, A52.
    fefd68f  A52. Scrap was counted twice in gross_production.
    81377fc  A14's documentation half: ESCROW.md and escrow-check.sh. 15 checks.
    9630192  The nightly Koorsus index backup, installed, verified 80 of 80.
    1dd7562  Repository: 64 files nothing ran, 41 .bak files, every __pycache__.
    d09e5da  The last seventeen, including a myarr.service pointing at a directory
             that had not existed for weeks.
    c5f5b4c  Audit: A28 to A32 closed.
    d7996a5  HANDOVER corrected in place, six statements. A41 and A42 close.
    db994ee  A53: restore.sh was Arkiv's script, not a wrong default. A54 recorded.
    ee61a4c  deploy/koorsus-scripts: the ten installed scripts, versioned.
    bd51f2a  A44: the real reason 5000 was still running.
    2f71e4a  The local token path (later reverted from this repository).
    3a3d571  koorsus-app imported. 0b70d68: reverted, see below.
    c432be7  A35: the temporary bridge that was built and taken down in 2026-11.
    ed4e366  This delta's predecessor, and HANDOVER pointing at it.
    912c68b  The legacy Koorsus on 5000 retired and archived.

On the other repository: `artifexofabrika/Arkiv` at 88502e1, "auth: a local token
for loopback callers". The Koorsus deployment then pins **989fa99**, which is
4550426 plus that one change.

## Decisions, so they are not relitigated

**A14 is closed on the owner's word.** Escrow is a documentation problem and a
maintenance habit; what a customer does with their own files is theirs. ESCROW.md
and escrow-check.sh exist and are tested. Do not reopen it because an envelope is
not physically sealed.

**Koorsus is Arkiv's codebase, not a second one.** It was imported into this
repository as koorsus-app/ and reverted inside the hour. `~/koorsus` is a clone of
`artifexofabrika/Arkiv`; its Python was byte-identical to 4550426; 4550426 is an
ancestor of Arkiv's f18c132, so it was 27 commits behind rather than diverged.
koorsus-app.service says it in its own header. **Read the deployment unit before
importing the application.** That sentence cost this session its largest mistake.

**The scripts have one home: deploy/koorsus-scripts/.** Ten files, byte-identical
to what is installed, with a README naming each one's state. Never edit the
installed copies; never treat ~/koorsus as the source.

**The local token lives in Arkiv, upstream.** Both deployments run that code, so a
Koorsus-only fork would mean merging every future Arkiv fix by hand. The gate
accepts a loopback caller holding the token, and only when the token file exists
and is non-empty: an appliance without it behaves exactly as before.

**No credential is persisted on an appliance.** The remote is SSH on both
repositories. The local token is an operating secret, not a convenience credential:
one per unit, mode 600, and it must never travel with a backup.

**History only grows.** No rebase, no force-push, no amend. Two commit subjects in
this session contain a literal `%s` where an apostrophe belonged; they stay, and
the lesson is that commit messages go through a file rather than printf.

## The legacy Koorsus on port 5000

It outlived its own replacement for one reason the audit had half right: its /ask
had no authentication, so the Myarra bot and the email agent used it while the
newer service on 5003 demanded a session neither had. The email agent was disabled
(the owner: it was never supposed to run), the bot moved to 5003 with the token, and
the service was stopped, disabled and masked. `serve.py`, `app.py`, `rag/`,
`email_skill.py`, `personal_graph.json` and `jeeves_persona.txt` are in
`legacy-koorsus-5000/` with a README, and the two unit files there are the installed
bytes, because the repository's own copies were stale.

`config.py` at the root is untracked, holds credentials, and is now read by nothing.
Deleting a secret is the owner's call.

## Proven, and not

Proven today: the bot answers from 5003 (a real Telegram reply, the document
service's own refusal sentence), `/ask` returns 401 without a token and 400 with
it, 5000 refuses connections and is masked, all suites green (test_rates 5,
test_bot_rates 19, test_floor_start 15, test_csv_roundtrip 8, test_pages 27,
test_line_card_rate_gap 16, test_herbie_veto 18, test-escrow-check 15,
test-usb-roundtrip 20, test_herbie_cards 5 cards with 0 vetoed).

Not proven, and not to be claimed: no human has touched /floor. A02 and A03 are
intermittent, and the card sweep is intermittent for the same reason. It was run at
the end of this session and came back 5 cards, 0 failed, 0 vetoed, including the
`unaccounted` card that had fabricated an operator quotation an hour earlier. One
green run is not evidence, which is precisely what A02 and A03 exist to say; what
the veto changes is that the next fabrication becomes a template instead of a
sentence in front of a plant manager.

## What remains

1. **The glass.** A device, a plant, a lead, five minutes. The only queue item left.
2. **A54's 27 commits.** Koorsus runs 989fa99, a recorded pin. Taking Arkiv's 27
   later commits is a deliberate update in a test window, not a cleanup.
3. **The local token is not in the installer or the backup manifest.** On a fresh
   unit the bot will say the document service is not set up until someone creates
   `/home/jeeves/.koorsus-local.token`. That belongs in install.sh (A19).
4. **32 open findings**, almost all notes. A51 (shift_reconciliations is written and
   read by nothing) and the A44-adjacent installer gaps are the ones with teeth.

## Corrections to earlier documents

The 11-23 delta's HEAD line and tracer claim are corrected in place. HANDOVER.md
had six statements true on 19 November and false now, all corrected in place,
including the two dangerous ones. A44's stated reason for 5000 surviving was half
the story. A35's docstring was false in three ways and is now true.

## Counts

53 findings, 21 fixed, 32 open. 312 tracked files.
