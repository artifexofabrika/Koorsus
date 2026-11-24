# Arkiv — Frequently Asked Questions

For prospective customers, their IT staff, and their managing partners.

## What is Arkiv?

Arkiv is a private document assistant that runs on an appliance in your
office. You ask questions in plain English, and Arkiv answers from your
firm's own documents, citing the source of every claim. If the answer is
not in the documents, Arkiv says so.

It is not a cloud service. It is not a subscription. It is a small box that
sits in your office, connects to your network, and does one thing well.

## What does Arkiv do?

- Answers questions from your firm's documents, with the exact source
  cited for every claim.
- Keeps documents organised by matter. You choose the matter before you
  ask, so a firm with a hundred active cases gets the right documents, not
  the closest match.
- Ingests text, Markdown, PDF, Word (.docx), and OpenDocument (.odt)
  files. Multiple files at once.
- Refuses to answer when the information is not in the documents. An
  honest "I do not find that" is better than a confident wrong answer.
- Runs entirely on the appliance. No outbound internet connection.
- Backs itself up nightly, encrypted, to a USB drive you keep in your safe.

## What does Arkiv not do?

- It does not give legal advice. It answers from documents and cites
  them. You draw the conclusions.
- It does not replace your case management system, billing system, or
  legal research databases.
- It does not draft documents.
- It does not connect to the internet. Ever. By design.
- It does not send your data anywhere.
- It does not read scanned PDFs that contain no text layer. If your
  documents are image-only scans, Arkiv cannot read them. We will tell
  you before you buy.

## Where does my data live?

On the appliance, in your office, on an encrypted disk. It does not leave
the appliance except as the encrypted backup you control.

## Is Arkiv connected to the internet?

No. The appliance has an Ethernet cable to your office network and nothing
else. There is no outbound connection, no telemetry, no update check, no
remote support tunnel. If a feature would require an internet connection,
we do not build it.

## How do I know the answers are correct?

Every answer cites the source document by name, and the text of the
passage it drew from. You can read the source and check it yourself. This
is the whole point of Arkiv: it does not ask you to trust it. It shows its
work.

When the documents do not contain the answer, Arkiv refuses. The refusal
is a feature, not a limitation. A confident wrong answer about a lockout
procedure or a filing deadline is a liability. An honest "I do not find
that" is not.

## How does matter scoping work?

Every document you ingest is tagged with a matter reference (a case
number, a client name, or whatever your firm uses). When you ask a
question, you choose which matter to search. Arkiv searches only that
matter's documents.

This is how a firm with a hundred active cases gets the right answer
instead of the closest one. If you have two clients named Henderson, the
matter tag is what separates them.

## What document formats does Arkiv accept?

- Plain text (.txt)
- Markdown (.md)
- PDF with a text layer (.pdf). Most PDFs generated from Word or a court
  filing system have a text layer. Scanned paper does not.
- Microsoft Word (.docx)
- OpenDocument Text (.odt)

## How many documents can Arkiv hold?

The capacity depends on the appliance tier. The limit is not disk space; it is the RAM available to hold the active search index. 

**Arkiv (Base tier, 8GB RAM).** Comfortable up to roughly 5,000 document chunks (approx. 500 to 1,000 pages of active documentation). This is ideal for solo practitioners and small firms (1-3 attorneys) with a manageable active caseload. Older, closed matters can be archived and loaded on demand.

**Arkiv NX (Mid tier, 16GB RAM).** Comfortable up to roughly 15,000 document chunks (approx. 2,000 to 3,000 pages). This is the right fit for a growing firm (4-10 attorneys) running multiple large cases simultaneously, or for a firm that wants to keep its entire five-year history active in the search index.

**Arkiv Thor (Enterprise tier, 128GB RAM).** Designed for large firms, massive document estates (100,000+ pages), and heavy concurrent usage. If your firm generates tens of thousands of pages of discovery per year, this is the appropriate appliance.

Every tier handles archives gracefully. You can ingest a thousand matters on the base tier, but you will keep roughly 30 to 50 active at a time and load the rest from the archive as needed.

## How many documents can Arkiv hold?

A single document estate of up to roughly 10,000 pages on the base
appliance. A typical small firm has three to five thousand pages of active
documentation per year. If you have more, the larger appliance handles
approximately five times that.

## How many people can use Arkiv at once?

The base appliance supports one person querying at a time. In practice,
this is fine for a firm of two to five attorneys: questions are answered
in a few seconds and the appliance is idle most of the day.

For a larger firm, or for simultaneous use by several staff, the larger
appliance supports up to five concurrent users.

## How do users sign in?

With a shared office PIN. The whole firm shares one PIN, and you store it
in your password manager. This is the same security model as the office
alarm code or the file room key: the people who work there have access,
and the appliance is not exposed to the internet.

If your firm needs to know which lawyer asked which question, the
per-user tier (available separately) adds named accounts and a query log.

## What about backups?

Arkiv backs itself up automatically every night at 3:00 AM. The backup is
encrypted with a passphrase your firm chooses and stores in its password
manager.

The safe ritual, once a week:

1. Friday afternoon, before leaving: insert the backup USB drive.
2. Monday morning: remove the USB drive and return it to your safe.

Three nightly backups run while the drive is inserted. The drive is not in
the appliance during the work week.

Every backup is checksummed when written, and verified weekly by an
automatic restore rehearsal. If a backup has failed, you will know before
you need it.

## What if the appliance is stolen?

Your documents are encrypted on the appliance's disk. Without the disk
encryption passphrase, the data cannot be read.

Your backups are encrypted with a separate passphrase. Without that
passphrase, the backup cannot be decrypted.

Artifexo does not hold either passphrase. We cannot read your documents,
and we cannot recover your data if the passphrases are lost. Store them in
your firm's password manager, and make sure at least two people have them.

## What if the appliance fails?

Call Artifexo before noon Eastern and we will arrange a replacement
shipped the same day where possible, or the next business day otherwise.

Your replacement appliance arrives with Arkiv pre-installed. Insert your
backup USB drive, type your passphrase, and your documents are back. Same
day, no cloud, no download, no waiting for us to restore your data.

## Can I access Arkiv from outside the office?

Not in the base configuration. The appliance is designed to be reachable
only from your office network. This is deliberate: it is why the appliance
has no public internet exposure and no attack surface from the outside.

A remote-access configuration is available as an upgrade. It uses an
encrypted tunnel to your office network, which preserves the same posture
(nothing exposed publicly, no cloud in the middle) while allowing lawyers
to reach Arkiv from home or from court. Ask us for details.

## Is Arkiv compliant with HIPAA or attorney-client privilege rules?

Arkiv is designed around the same principles those rules require:
- The appliance never transmits data outside your office.
- The disk is encrypted.
- Backups are encrypted and stored in your safe.
- Access is gated by a PIN.

Compliance is ultimately your firm's responsibility, and it depends on how
your firm configures and uses the appliance. What we can say honestly:
- Nothing leaves your office.
- Nothing is sent to any third party.
- No employee of Artifexo has access to your documents.
- The appliance is not a covered entity and does not function as a
  business associate in the HIPAA sense, because it does not transmit
  or store data on behalf of your firm outside your firm.

We will provide a written security overview for your firm's compliance
review, and we will answer questions from your IT staff or outside counsel
before purchase.

## What does it cost?

Base appliance: $2,500, installed and configured.
Larger appliance (for firms with five or more concurrent users, or larger
document estates): $3,500 to $4,000.

Pricing includes installation, configuration, and a walk-through for your
office manager. It does not include extended support, which is available
separately.

## What is included?

- The appliance, configured and tested.
- Installation on your office network.
- A one-hour walk-through with the office manager.
- The Quick Start card and a laminated reference for the office.
- One year of warranty on the hardware.
- The software is open source. You own the appliance. If you want to
  inspect, modify, or run the software yourself, you can.

## What about support?

Included: email support for the first thirty days, plus the warranty.
Available separately: a support plan that covers telephone support, remote
diagnosis (with your permission and only within your network), and
priority replacement if the appliance fails.

## What about upgrades?

The software improves over time. We will provide software updates as they
are ready. Each update is applied by us on a scheduled visit or, if you
prefer, by your IT staff following a written procedure we provide.

Hardware upgrades, such as a larger disk or a faster appliance, are
available at any time. Your documents and backups carry over.

## What if I want my documents out?

Two ways. The original files were never deleted from your systems; you
keep the originals. And the appliance provides a full export of every
document it has indexed. If you stop using Arkiv, you take everything out
and there is nothing for us to hold.

## What are the honest limits?

- Arkiv is not a defense against a nation-state attacker. It is secured
  to the standard a small professional firm needs. No appliance in this
  price class is a defense against a determined government.
- Arkiv does not replace a lawyer's judgment, and it does not give legal
  advice.
- Arkiv reads documents with a text layer. Scanned paper requires a
  separate scanning step before ingestion.
- The shared PIN means every staff member can see every document in the
  library. Per-user access controls are available in the per-user tier.
- Arkiv will not answer every question. When the documents do not contain
  the answer, it refuses. That is by design.

## How do I get started?

Call or write. We will schedule a fifteen-minute conversation to understand
your firm's document volume and workflows, and we will tell you honestly
whether Arkiv is a fit. If it is, we will schedule installation, which
takes an afternoon.

---

Artifexo Fabrika
Columbus, Ohio
[phone] | [email]
