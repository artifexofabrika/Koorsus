#!/bin/bash
# Koorsus collection reset -- REFUSES, on purpose. Written 2026-11-24.
#
# This file was Arkiv's factory reset. It stopped arkiv.service, moved
# /mnt/lake/arkiv_index aside, created an empty one, started arkiv.service and
# checked port 5001. On a box where both products run, that does two things:
#
#   it empties the Arkiv document library
#   it leaves the Koorsus collection exactly as it was
#
# which is the opposite of what this name promises, in a script whose failure
# mode is somebody's document estate. It was never renamed when five of its
# neighbours were (A53).
#
# A Koorsus reset is a real need before any customer install: the collection
# still holds our own test documents (A17). It is not this script, and it has not
# been written. The safe shape is here to copy: move the index aside rather than
# delete it, require a typed confirmation, stop and start koorsus-app.service,
# check the Koorsus port, and test it against a scratch index directory rather
# than the live one.
set -euo pipefail

cat >&2 <<'MSG'
REFUSED. This is not a Koorsus reset script.

  The script that used to be here resets Arkiv. It stops arkiv.service, moves
  /mnt/lake/arkiv_index aside and creates an empty one. Run on this appliance it
  would empty the Arkiv library and leave Koorsus untouched.

  There is no Koorsus reset yet. A17 and A53 in deploy/AUDIT.md say why, and
  what it has to do before a customer install.
MSG
exit 1
