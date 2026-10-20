#!/usr/bin/env python3
"""Email agent for Koorsus. Polls Gmail, forwards questions to Koorsus, replies."""

import imaplib
import smtplib
import email
import time
import config
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
USERNAME = config.EMAIL_USERNAME
PASSWORD = config.EMAIL_APP_PASSWORD
ALLOWED = [a.strip().lower() for a in config.EMAIL_ALLOWED_SENDERS.split(",")]
KOORSUS_URL = "http://127.0.0.1:5000/ask"


def decode_subject(raw):
    if not raw:
        return ""
    parts = decode_header(raw)
    subject, encoding = parts[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding or "utf-8", errors="replace")
    return subject


def extract_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="replace")[:2000]
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    import re
                    html = payload.decode("utf-8", errors="replace")
                    return re.sub(r"<[^>]+>", "", html).strip()[:2000]
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode("utf-8", errors="replace")[:2000]
    return ""


def extract_address(sender_field):
    import re
    m = re.search(r"<(.+?)>", sender_field)
    return (m.group(1) if m else sender_field).strip().lower()


def ask_koorsus(question):
    try:
        r = requests.post(KOORSUS_URL, json={"question": question}, timeout=90)
        d = r.json()
        ans = d.get("answer", "(no answer)")
        src = d.get("sources", [])
        return f"{ans}\n\n--- {', '.join(src)}" if src else ans
    except Exception as e:
        return f"Koorsus unreachable: {e}"


def send_reply(to_address, subject, body):
    msg = MIMEMultipart()
    msg["From"] = USERNAME
    msg["To"] = to_address
    msg["Subject"] = "Re: " + subject
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(USERNAME, PASSWORD)
            smtp.sendmail(USERNAME, to_address, msg.as_string())
        return True
    except Exception as e:
        print(f"SMTP error: {e}")
        return False


def check_once():
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(USERNAME, PASSWORD)
        mail.select("INBOX")
        status, data = mail.search(None, "UNSEEN")
        if status != "OK":
            mail.logout()
            return
        for num in data[0].split():
            status, msg_data = mail.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            sender = extract_address(msg.get("From", ""))
            subject = decode_subject(msg.get("Subject", ""))
            body = extract_body(msg)
            print(f"From: {sender} | Subject: {subject}")
            if sender not in ALLOWED:
                print(f"  Ignored (sender not on allowlist)")
                mail.store(num, "+FLAGS", "\\Seen")
                continue
            answer = ask_koorsus(body)
            if send_reply(sender, subject, answer):
                print(f"  Replied.")
            mail.store(num, "+FLAGS", "\\Seen")
        mail.logout()
    except Exception as e:
        print(f"IMAP error: {e}")


def main():
    print("Koorsus email agent running. Poll every 60 seconds.")
    while True:
        check_once()
        time.sleep(60)


if __name__ == "__main__":
    main()
