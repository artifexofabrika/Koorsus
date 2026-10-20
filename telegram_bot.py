#!/usr/bin/env python3
"""Telegram bridge to Koorsus RAG."""

import time
import requests
import config

BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
CHAT_ID = config.TELEGRAM_CHAT_ID
KOORSUS_URL = "http://127.0.0.1:5000/ask"
API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(text):
    url = f"{API}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    try:
        r = requests.post(url, json=data, timeout=10)
        if r.status_code == 200:
            print(f"Sent: {text[:50]}...")
        else:
            print(f"Send error: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Send error: {e}")


def get_updates(offset=None):
    url = f"{API}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    try:
        r = requests.get(url, params=params, timeout=35)
        if r.status_code == 200:
            return r.json().get("result", [])
    except Exception as e:
        print(f"Update error: {e}")
    return []


def ask_koorsus(question):
    try:
        r = requests.post(KOORSUS_URL, json={"question": question}, timeout=90)
        d = r.json()
        ans = d.get("answer", "(no answer)")
        src = d.get("sources", [])
        return f"{ans}\n\n--- {', '.join(src)}" if src else ans
    except Exception as e:
        return f"Koorsus unreachable: {e}"


def main():
    print("Koorsus Telegram bridge running.")
    offset = None
    while True:
        try:
            for update in get_updates(offset):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "").strip()
                if not text:
                    continue
                if chat_id != CHAT_ID:
                    continue
                print(f"Received: {text}")
                send_message(ask_koorsus(text))
            time.sleep(1)
        except Exception as e:
            print(f"Main loop error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
