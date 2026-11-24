#!/usr/bin/env python3
"""A44: the local token path into Koorsus, and the bot's use of it.

Two halves, and either one alone proves nothing. auth.py must let a loopback
caller holding the token through, and must refuse everyone else. bot/support.py
must actually send the header, parse the answer, and say something true when the
service refuses it.

The Koorsus app is not running for this test and is not needed. auth.py is
imported with its three neighbours stubbed, mounted on a bare Flask app; the bot's
HTTP is pointed at a throwaway server in a thread that records what it received.

Run: /home/jeeves/jeeves-env/bin/python tools/test_local_token.py
Exit 0 when every check passes, 1 when any fails, 2 when it cannot start.
"""
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "koorsus-app"))
sys.path.insert(0, os.path.join(ROOT, "myarr_v2"))

WORK = tempfile.mkdtemp(prefix="myarra_localtoken_")
TOKEN_FILE = os.path.join(WORK, "local.token")
os.environ["KOORSUS_LOCAL_TOKEN_FILE"] = TOKEN_FILE
os.environ["KOORSUS_SOP_URL"] = "http://127.0.0.1:9/ask"   # deliberately closed

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    line = ("PASS  " if ok else "FAIL  ") + name
    if not ok and detail:
        line += "\n        " + str(detail)[:400]
    print(line)


def write_token(value):
    with open(TOKEN_FILE, "w") as fh:
        fh.write(value)


try:
    # auth.py imports config, users and templates_html. The live app has all
    # three; here they are stubs so the test needs no database and no secrets.
    cfg = types.ModuleType("config")
    cfg.ARKIV_PIN = "0000"
    sys.modules["config"] = cfg
    us = types.ModuleType("users")
    us.count_users = lambda: 1
    us.verify = lambda username, pin: None
    sys.modules["users"] = us
    th = types.ModuleType("templates_html")
    th.LOGIN_PAGE = "login"
    sys.modules["templates_html"] = th

    from flask import Flask
    import auth
    from bot import support
except Exception as exc:                                    # noqa: BLE001
    print("CANNOT START: %s" % exc)
    shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(2)

app = Flask(__name__)
app.secret_key = "test-only"
auth.register(app)


@app.route("/ask", methods=["POST"])
def _ask():
    return {"answer": "ok", "sources": [], "matters_found": []}


client = app.test_client()
LOCAL = {"REMOTE_ADDR": "127.0.0.1"}
REMOTE = {"REMOTE_ADDR": "10.1.1.1"}


def post(headers=None, environ=None):
    return client.post("/ask", json={"question": "x"},
                       headers=headers or {}, environ_base=environ or LOCAL)


# ---------------------------------------------------------------- auth side

write_token("s3cret-local-token\n")
check("a loopback caller holding the token is let through",
      post({"X-Koorsus-Token": "s3cret-local-token"}).status_code == 200,
      post({"X-Koorsus-Token": "s3cret-local-token"}).status_code)

write_token("  s3cret-local-token  \n")
check("surrounding whitespace in the token file is stripped",
      post({"X-Koorsus-Token": "s3cret-local-token"}).status_code == 200,
      "a token file written with echo or spaces should still match")

write_token("s3cret-local-token\n")
check("a wrong token is refused",
      post({"X-Koorsus-Token": "not-the-token"}).status_code == 401,
      post({"X-Koorsus-Token": "not-the-token"}).status_code)

check("no token at all is refused",
      post().status_code == 401, post().status_code)

check("the right token from a non-loopback address is refused",
      post({"X-Koorsus-Token": "s3cret-local-token"}, REMOTE).status_code == 401,
      post({"X-Koorsus-Token": "s3cret-local-token"}, REMOTE).status_code)

write_token("")
check("an empty token file opens nothing, even for an empty header",
      post({"X-Koorsus-Token": ""}).status_code == 401,
      post({"X-Koorsus-Token": ""}).status_code)

os.remove(TOKEN_FILE)
check("a missing token file opens nothing",
      post({"X-Koorsus-Token": "s3cret-local-token"}).status_code == 401,
      post({"X-Koorsus-Token": "s3cret-local-token"}).status_code)

check("a browser GET still redirects to the login page",
      client.get("/", environ_base=LOCAL).status_code == 302,
      client.get("/", environ_base=LOCAL).status_code)

check("the login page itself is still reachable without a token",
      client.get("/login", environ_base=LOCAL).status_code == 200,
      client.get("/login", environ_base=LOCAL).status_code)

# ----------------------------------------------------------------- bot side

STATE = {"status": 200, "token": None, "body": None}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        STATE["token"] = self.headers.get("X-Koorsus-Token")
        try:
            STATE["body"] = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            STATE["body"] = None
        payload = json.dumps({"answer": "the answer from the service"}).encode()
        self.send_response(STATE["status"])
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
support.SOP_URL = "http://127.0.0.1:%d/ask" % server.server_address[1]

write_token("s3cret-local-token")
reply = support.h_sop(None, None, "sop what is a capper?", None)
check("the bot returns the service's answer",
      reply == "the answer from the service", reply)

check("the bot sent the local token",
      STATE["token"] == "s3cret-local-token", STATE["token"])

check("the bot sent the question with its command prefix stripped",
      (STATE["body"] or {}).get("question") == "what is a capper?",
      STATE["body"])

STATE["status"] = 401
reply = support.h_sop(None, None, "sop anything", None)
check("a rejected token produces a sentence, not a dictionary",
      "rejected the bot's token" in reply and "{" not in reply, reply)

os.remove(TOKEN_FILE)
reply = support.h_sop(None, None, "sop anything", None)
check("no token file produces a sentence saying so, and sends nothing",
      "not set up" in reply, reply)

server.shutdown()

failed = RESULTS.count(False)
print("")
print("%d checks, %d failed" % (len(RESULTS), failed))
if failed:
    print("Work directory kept: " + WORK)
else:
    shutil.rmtree(WORK, ignore_errors=True)
sys.exit(1 if failed else 0)
