# The legacy Koorsus on port 5000

What ran here, why it stopped, and what runs instead.

## What this was

A second Koorsus application, the older generation, started by `koorsus.service`
on port 5000 and served by `serve.py` with waitress. Its `/ask` endpoint had no
authentication at all, which is why it outlived its replacement: the Myarra bot's
SOP handler and the email agent both posted to it, and neither had a credential to
offer the newer service.

Retired on **2026-11-24**, when the bot moved to the Koorsus on 5003 with a
loopback token (A44). The unit was stopped and disabled; masking it needs the
installed unit file removed first, because a mask is a symlink and one cannot sit
where a real file does.

## What is in here

    serve.py            waitress entry point for the 5000 app
    app.py              the older Koorsus application
    rag/                its retrieval package, self-contained
    email_skill.py      the email agent's handler, which posted to 5000/ask
    personal_graph.json data file for the old app
    jeeves_persona.txt  persona text for the email agent
    koorsus.service     the INSTALLED unit, copied from /etc/systemd/system
    email-agent.service the INSTALLED unit, copied from /etc/systemd/system

The two unit files here are the installed bytes, not the copies that used to sit
in the repository root. Those were stale: the root `koorsus.service` still named
`llama-server.service` where the machine ran `koorsus-llm.service`. An archive
that preserves the wrong version is worse than none, so the faithful one was
copied out of `/etc` before the file was removed.

## What runs instead

- **Documents on 5003**: the Koorsus application, which is the Arkiv codebase
  deployed a second time under a different configuration. Its pinned commit is
  recorded in A54.
- **The bot's SOP answers**: `myarr_v2/bot/support.py` posts to
  `https://127.0.0.1:5003/ask` with a loopback token, and this repository's
  `deploy/koorsus-scripts/` holds the scripts that back that service up.
- **The email agent**: disabled, and not supposed to be running on an appliance.

## What was not archived

`config.py` at the repository root holds credentials. It is untracked and
gitignored, it stayed on disk, and as of this archive it is read by nothing.
Whoever owns the appliance should decide whether it is still needed.

## If any of this is ever wanted again

It is in git history, and the history is the reason this directory could be moved
rather than deleted.
