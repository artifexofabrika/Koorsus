# SESSION DELTA 2026-11-24 — WHAT A NEW INSTANCE SHOULD KNOW FIRST

Follows SESSION-DELTA-2026-11-23.md. HEAD at close: c432be7. Everything below was
verified on the reference Jetson. Where it says a thing is not live, believe that
over any code you find on disk.

Read in this order: PHILOSOPHY.md, deploy/STATE.md, deploy/AUDIT.md, then this.
That is the order HANDOVER.md now prescribes, and it is the order that would have
saved this session its first hour.

## What was true when the session began

The delta before this one said HEAD was fd670a5 and that the tracer "already
detects a narrative containing a number the payload does not carry, and only
warns". The second was false: nothing in the product traced anything, and the only
tracer was a print inside tools/test_herbie_cards.py comparing against the stats
dictionary rather than the prompt. The first was stale by two commits, one of them
the delta's own.

The queue was four items: A01's Telegram half, the tracer veto, A14 and A16, and a
human on the glass.

## Shipped, in order

    a709d1b  A01's bot half. ideal_rate() returns None; five call sites handled;
             the dead duplicate in bot/resolve.py deleted. 19 checks.
    17e3c01  Audit: A01 closed, A50 recorded.
    aae0467  A50. The view keeps rows a missing rate used to delete, and the line
             card says unknown instead of zero. 16 checks.
    e61eae7  The tracer veto. Traced against the whole prompt, not the stats; one
             implementation shared with the card sweep. 18 checks.
    16a1e67  Records: the delta's two false statements, the route count, A51, A52.
    fefd68f  A52. Scrap was counted twice in gross_production. Capacity gaps
             change as a result.
    81377fc  A14's escrow half: ESCROW.md and escrow-check.sh. 15 checks.
    9630192  The nightly Koorsus index backup, installed and verified 80 of 80
             documents.
    1dd7562  Repository cleanup: 64 files nothing ran, 41 .bak files, every
             __pycache__.
    d09e5da  The last seventeen: archive/, test.txt, duplicate screenshots, a
             myarr.service pointing at a directory that no longer exists.
    c5f5b4c  Audit: A28 to A32 closed.
    d7996a5  HANDOVER corrected in place, six statements. A41 and A42 close.
    db994ee  A53: restore.sh was Arkiv's script, not a wrong default. A54 recorded.
    ee61a4c  deploy/koorsus-scripts: the ten installed scripts, versioned.
    bd51f2a  A44: the real reason 5000 is still running.
    3a3d571  koorsus-app imported. 2f71e4a: the local token. 0b70d68: the import
             REVERTED, see below. c432be7: A35.

## The decisions, so they are not relitigated

**A14 is closed on the owner's word.** Escrow is a documentation problem and a
maintenance habit; what a customer does with their own files is theirs. ESCROW.md
and escrow-check.sh exist and are tested. Do not reopen it because the envelope is
not physically sealed.

**The Koorsus application does not get a repository in this repository.** It was
imported as koorsus-app/ and reverted within the hour. `~/koorsus` is a clone of
github.com/artifexofabrika/Arkiv at 4550426; its Python is byte-identical to that
commit; 4550426 is an ancestor of Arkiv's f18c132, so it is 27 commits behind, not
diverged. koorsus-app.service says it in its own header: "Koorsus is the Arkiv
codebase deployed a second time under a different configuration. It is not a
second codebase." Read the deployment unit before importing the application.

**The scripts have one home: deploy/koorsus-scripts/.** Ten files, byte-identical
to what is installed, with a README naming each one's state. Change there, commit,
copy to /usr/local/sbin/koorsus. Never edit the installed copies, never treat
~/koorsus as the source.

**The local token belongs in the Arkiv codebase,** because both products share it.
The code is in history at 2f71e4a and is not in the tree. Nothing reads the token
file yet; it exists at /home/jeeves/.koorsus-local.token, owner only.

**No credential is ever persisted on an appliance.** No credential.helper store,
no token in a remote URL. The remote is SSH at git@github.com and verified.
deploy/STATE.md carries this rule and the pre-push commit listing beside it.

## Not proven, do not claim it

- No human has ever touched /floor. Every claim about start, end and the switches
  is Flask's test client.
- test_herbie_cards has not been run since the last restart, because the running
  process is older than the tracer fix. It will refuse with exit 2 until myarr is
  restarted. That refusal is correct behaviour, not a failure.
- The token path works in a pre-flight only: /login 200, /ask 401 without a token,
  400 with the right one, run against the imported copy that has since been
  deleted. It has never been exercised against the running service.

## What to do next, in this order

1. Commit the local token path to the Arkiv codebase (recover it from 2f71e4a),
   and keep 4550426 as Koorsus's pin until a deliberate update. Then point
   ~/koorsus at a commit that contains it, so the running tree stays clean.
2. Create the token file on the unit, restart koorsus-app, and prove /ask with the
   token returns 400 on an empty question and 401 without it.
3. Repoint myarr_v2/bot/support.py — it is already written to https://127.0.0.1:5003
   with the header — restart myarra-bot, and test "sop <question>" through Telegram.
4. Only then stop, disable and mask koorsus.service on 5000, and archive serve.py
   and app.py into a TRACKED directory. archive/ is gitignored and would take them
   out of the record rather than into it. email-agent.service is already disabled;
   email_skill.py is dead code once it is.
5. A54: record which Arkiv commit runs, and decide when to take the 27 commits.

## Corrections to earlier documents

The 11-23 delta's HEAD line and its tracer claim are corrected in place, with
dates. HANDOVER.md had six statements that were true on 19 November and are not
now; all six are corrected in place, including the two dangerous ones (it told a
reader to ignore the live Koorsus, and that backups did not exist). A44's stated
reason for port 5000 surviving was half the story: it is not a Telegram bot, it is
that /ask on 5003 requires authentication and the bot has no session.

## Counts

53 findings, 21 fixed, 32 open. The 32 are not the road to a pilot; the four-item
queue is, and three of its four are done.
