import os
import json
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

TO_EMAIL = os.environ.get("TO_EMAIL", "jacek@pacior.lap.pl")

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.pacior.lap.pl")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASS = os.environ["SMTP_PASS"]

STATE_FILE = "state_seen.json"
FORCE_TEST_EMAIL = os.environ.get("FORCE_TEST_EMAIL", "0") == "1"

URLS = [
    "https://www.pfron.org.pl/aktualnosci/",
    "https://www.pfron.org.pl/komunikaty/",
]

KEYWORDS = [
    "nabór", "tura", "wniosek", "wniosków",
    "program", "dofinansowanie",
    "Samodzielność", "Aktywność", "Mobilność",
    "Aktywny Samorząd", "SOW", "PFRON"
]

def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(seen))[-2000:], f, ensure_ascii=False, indent=2)

def normalize_url(link):
    if link.startswith("//"):
        return "https:" + link
    if link.startswith("/"):
        return "https://www.pfron.org.pl" + link
    return link

def looks_relevant(title):
    t = title.lower()
    return any(k.lower() in t for k in KEYWORDS)

def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # STARTTLS dla portu 587 (Brevo)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


def extract_items(url):
    r = requests.get(url, timeout=25, headers={"User-Agent": "pfron-agent/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    items = []
    for a in soup.find_all("a", href=True):
        title = " ".join(a.get_text(" ", strip=True).split())
        href = normalize_url(a["href"])
        if not title or len(title) < 6:
            continue
        items.append((title, href))
    return items

def main():
    seen = load_seen()
    new_found = []

    for url in URLS:
        for title, link in extract_items(url):
            if not looks_relevant(title):
                continue
            key = f"{title}::{link}"
            if key not in seen:
                seen.add(key)
                new_found.append((title, link, url))

    if FORCE_TEST_EMAIL:
        send_email(
            "TEST: PFRON agent – SMTP działa",
            "To jest mail testowy z GitHub Actions. Jeśli go widzisz, SMTP działa poprawnie."
        )

    elif new_found:
        new_found = new_found[:25]
        subject = f"PFRON – nowe ogłoszenia ({len(new_found)})"
        body = "Wykryto nowe komunikaty PFRON:\n\n"
        for t, l, src in new_found:
            body += f"- {t}\n  {l}\n  źródło: {src}\n\n"
        body += "Automatyczne powiadomienie."
        send_email(subject, body)

    save_seen(seen)

if __name__ == "__main__":
    main()
