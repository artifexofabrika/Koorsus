#!/usr/bin/env bash
# Nightly smoke run: exercise the appliance, record the verdict.
set -euo pipefail

STATUS=/var/log/arkiv-smoke.status
cd /home/jeeves/arkiv

set +e
OUT=$(/home/jeeves/jeeves-env/bin/python smoke.py 2>&1)
RC=$?
set -e

SUMMARY=$(printf '%s\n' "$OUT" | tail -n1)
STAMP=$(date -Is)

if [ "$RC" -eq 0 ]; then
  printf 'OK|%s|%s\n' "$STAMP" "$SUMMARY" > "$STATUS"
else
  printf 'FAIL|%s|%s\n' "$STAMP" "$SUMMARY" > "$STATUS"
fi

/home/jeeves/jeeves-env/bin/python - <<'PY' >/dev/null 2>&1 || true
import users
for u in users.list_users():
    if u["name"] == "smoke":
        users.delete_log(u["id"])
PY

exit 0
