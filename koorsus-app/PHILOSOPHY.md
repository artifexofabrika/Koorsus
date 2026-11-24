# Arkiv — Philosophy and Inviolable Commitments

This document governs Arkiv. It is never superseded. Every future session
delta, every product decision, and every marketing claim either conforms to
it or is wrong. Only the owner may revise it.

Companion document: the Myarra philosophy, PHILOSOPHY.md in the Koorsus
repository. The two products share a posture and have different subjects.
Myarra measures the floor. Arkiv reads the office.

## What Arkiv is for

A small law firm, medical practice, or professional office runs on documents.
Contracts, pleadings, discovery, correspondence, policies, procedures,
prior work product. The documents are the substance of the practice, and
almost none of them are reachable by search. The lawyer remembers the case,
not the paragraph. The paralegal knows which file has the clause, until
they leave.

The general-purpose AI tools solve this by sending the documents to
someone else's server. That is unacceptable for a firm whose privilege
obligations follow every page. The cloud tools know this, and they offer
enterprise agreements and private instances at prices a small firm cannot
pay.

Arkiv exists to give the small firm the same capability at a price it can
afford, with a posture its partners can defend: the documents never leave
the office, and the appliance belongs to the firm.

## The five commitments

### 1. The documents never leave the office.

No cloud. No telemetry. No vendor access. No update check. No remote
tunnel we operate. The appliance has an Ethernet cable to the office
network and nothing else, by design and by default.

Remote access, when a firm chooses it as an upgrade, runs through an
encrypted tunnel to the firm's own network. The appliance still talks to
no one but the firm. The posture holds.

What this forbids: any feature that would require an outbound connection
to a service we operate or a third party provides. If the feature cannot
be built without egress, we do not build it.

### 2. The refusal is the feature.

A confident wrong answer about a filing deadline, a lockout procedure, or
a contract term is a liability. An honest "I do not find that in the
documents" is not. Arkiv's value is not that it answers every question. It
is that its answers can be trusted.

How the refusal works, concretely:

- Retrieval comes before generation. The model sees the retrieved passages
  and the question. It does not see the question alone with an invitation
  to answer from training data.
- The refusal happens in two places. If retrieval finds nothing relevant,
  the system refuses before the model runs. If retrieval finds passages
  but the model cannot find the answer in them, the prompt instructs it
  to say so plainly, and the response is checked against refusal patterns
  before it reaches the lawyer. The refusal is a code path, not a hope.
- Every answer carries the passage, not just the document name. The lawyer
  reads the source and the answer side by side.
- Every refusal is logged. A firm can audit what the system declined to
  answer and whether the refusal was correct.

What this forbids: any feature that makes the system more willing to
answer at the cost of being less certain. Speed, fluency, and coverage
are subordinate to trustworthiness. A refusal that is correct is better
than an answer that might be.

### 3. The matter is the container.

A law firm thinks in matters. A medical office thinks in patients. A
professional office thinks in engagements. Arkiv organises documents the
way the office organises them, not the way a search engine does.

The lawyer chooses the matter before asking. The system searches only
that matter's documents. A firm with a hundred active cases gets the
right answer, not the closest one. This is the difference between Arkiv
and a general-purpose document search.

Cross-matter search is also available, because sometimes the question is
"find every case where this expert was deposed." That is a deliberate
choice the lawyer makes, not a default. The default is one matter.

What this forbids: any default that searches everything, and any design
that requires the lawyer to remember which documents are in which matter.
The matter is the container the system respects.

### 4. The customer owns the appliance.

No subscription. No lock-in. No data hostage. The software is
source-available under the Functional Source License, which means the firm
receives the source, can modify it for its own use, and can hand it to a
third-party developer to maintain. It cannot be resold as a competing
product. Each released version becomes fully open source two years after
its release.

The appliance belongs to the firm. If they stop paying us, the appliance
still works. Their documents remain theirs. Their backups remain theirs.
Their passphrases remain theirs.

What this forbids: any design that would stop working if our company
disappeared, and any claim of ownership over the customer's data or the
customer's system. We sell the appliance, the installation, the support,
and the maintenance. We do not sell a lease.

### 5. The backup is proven, not assumed.

A backup that has not been tested by restoring it is not a backup. It is a
hope. We have seen the failure mode: an archive that looks fine until the
day it is needed, and then cannot be opened.

Every backup is:
- Checksummed when written, so silent corruption is detected.
- Encrypted with a passphrase the firm holds, so a stolen backup is
  useless to a thief.
- Verified weekly by an automatic restore rehearsal that opens the
  archive, runs a SQLite integrity check, and counts the documents. If
  the count does not match, the firm is notified before they need the
  backup.

What this forbids: any change to the backup path that skips the
verification, and any feature that stores a backup where the firm cannot
reach it.

## The test for any proposed feature

Ask, in order:

1. Does it keep the documents inside the office?
2. Does it preserve the refusal, or does it trade trust for fluency?
3. Does it respect the matter as the container?
4. Does it work if our company disappears tomorrow?
5. Does it leave the backup path proven and restorable?

A feature that fails any of these is not an Arkiv feature, whatever else
it may be.

## The honest limits

Arkiv is secured to the standard a small professional firm needs. It is
not a defense against a nation-state attacker, and no appliance in this
price class is. It does not replace a lawyer's judgment, and it does not
give legal advice. It reads documents with a text layer; scanned paper
requires a scanning step. The shared PIN means every staff member can
see every document in the library; per-user access controls are an
upgrade tier.

These are stated plainly because a product that overstates what it does
is worse than one that states its limits. The firm should buy Arkiv
knowing what it does and does not do.

END OF PHILOSOPHY.
