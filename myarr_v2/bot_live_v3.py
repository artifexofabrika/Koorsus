"""Live Telegram loop using bot_v3 dispatch."""
import time, sys, os, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from bot_v2 import get_conn, ensure_schema, get_user_by_tg
from bot.db import Session
from bot.dispatch import dispatch

TOKEN = config.TELEGRAM_BOT_TOKEN
API = f"https://api.telegram.org/bot{TOKEN}"

def send(chat_id, text):
    if not text: return
    for i in range(0, len(text), 4000):
        try:
            requests.post(f"{API}/sendMessage",
                          json={"chat_id": chat_id, "text": text[i:i+4000]},
                          timeout=15)
        except Exception as e:
            print(f"send error: {e}", file=sys.stderr)

def main():
    conn = get_conn(); ensure_schema(conn)
    me = requests.get(f"{API}/getMe", timeout=10).json()
    print(f"bot_live_v3: polling as @{me['result']['username']}", flush=True)
    offset = None
    while True:
        try:
            params = {"timeout": 25}
            if offset: params["offset"] = offset
            r = requests.get(f"{API}/getUpdates", params=params, timeout=35)
            data = r.json()
            if not data.get("ok"):
                print(f"getUpdates not ok: {data}", file=sys.stderr); time.sleep(5); continue
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = (msg.get("text") or "").strip()
                if not chat_id or not text: continue
                user = get_user_by_tg(conn, chat_id)
                if not user:
                    send(chat_id, f"Unauthorized. Your Telegram ID is {chat_id}.")
                    continue
                sess = Session(conn, chat_id)
                try:
                    reply = dispatch(conn, sess, text, user)
                except Exception as e:
                    reply = f"Internal error: {e}"
                    print(f"dispatch error for {chat_id}: {e}", file=sys.stderr)
                send(chat_id, reply)
        except KeyboardInterrupt: break
        except Exception as e:
            print(f"loop error: {e}", file=sys.stderr); time.sleep(5)
    conn.close()

if __name__ == "__main__":
    main()
