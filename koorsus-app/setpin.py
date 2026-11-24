"""Set a user's PIN. Usage: setpin.py <name> <pin>"""
import sys
import users

if len(sys.argv) != 3:
    raise SystemExit("usage: setpin.py <name> <pin>")

target = [u for u in users.list_users() if u["name"] == sys.argv[1]]
if not target:
    raise SystemExit("no such user: " + sys.argv[1])
users.set_pin(target[0]["id"], sys.argv[2])
print("PIN set for " + sys.argv[1])
