import smtplib
import time
from email.message import EmailMessage

import config

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def send_emails(
    messages: list,
    gmail_user: str = None,
    gmail_password: str = None,
    sender_name: str = None,
    send_delay: float = None,
) -> tuple:
    gmail_user = (gmail_user or config.GMAIL_USER).strip()
    gmail_password = (gmail_password or config.GMAIL_APP_PASSWORD).strip()
    sender_name = (sender_name or config.SENDER_NAME).strip()
    send_delay = send_delay if send_delay is not None else config.SEND_DELAY

    if not gmail_user or not gmail_password:
        raise SystemExit(
            "Missing Gmail credentials. Enter your Gmail address and App Password "
            "in the Settings section of the page (or .env). Gmail requires an App "
            "Password: Google Account > Security > 2-Step Verification > App passwords."
        )

    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
    server.ehlo()
    server.starttls()
    server.login(gmail_user, gmail_password)

    sent, failed = [], []
    for message in messages:
        msg = EmailMessage()
        msg["From"] = f"{sender_name} <{gmail_user}>"
        msg["To"] = message["email"]
        if message.get("cc"):
            msg["Cc"] = message["cc"]
        msg["Subject"] = message["subject"]
        msg.set_content(message["body"])
        try:
            server.send_message(msg)
            sent.append(message["email"])
            print("  sent:", message["email"])
        except Exception as exc:
            failed.append((message["email"], str(exc)))
            print("  FAILED:", message["email"], "-", exc)
        time.sleep(send_delay)

    server.quit()
    return sent, failed
