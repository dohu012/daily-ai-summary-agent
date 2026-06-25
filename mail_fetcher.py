import email
import imaplib
import re
from dataclasses import dataclass, field
from datetime import datetime
from email.header import decode_header
from typing import Optional

from bs4 import BeautifulSoup

from config import config


@dataclass
class MailItem:
    uid: str
    subject: str
    sender: str
    date: datetime
    body_text: str
    processed: bool = False


def _decode_header_value(raw: str) -> str:
    parts = decode_header(raw)
    decoded = ""
    for part, charset in parts:
        if isinstance(part, bytes):
            charset = charset or "utf-8"
            try:
                decoded += part.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                decoded += part.decode("utf-8", errors="replace")
        else:
            decoded += str(part)
    return decoded


def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "img", "nav", "footer", "head"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _parse_date(raw: str) -> datetime:
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(raw)
    except (ValueError, TypeError):
        return datetime.now()


def _extract_body(msg: email.message.Message) -> str:
    text_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        text_parts.append(payload.decode(charset, errors="replace"))
                    except (LookupError, UnicodeDecodeError):
                        text_parts.append(payload.decode("utf-8", errors="replace"))
            elif content_type == "text/html" and not text_parts:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        html = payload.decode(charset, errors="replace")
                    except (LookupError, UnicodeDecodeError):
                        html = payload.decode("utf-8", errors="replace")
                    text_parts.append(_clean_html(html))
    else:
        content_type = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                raw = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                raw = payload.decode("utf-8", errors="replace")
            if content_type == "text/html":
                text_parts.append(_clean_html(raw))
            else:
                text_parts.append(raw)

    return "\n\n".join(text_parts)


class MailFetcher:
    def __init__(self, seen_uids: Optional[set[str]] = None):
        self._seen_uids = seen_uids or set()

    def fetch_unread(self, limit: int = 30) -> list[MailItem]:
        conn = imaplib.IMAP4_SSL(config.imap_server, config.imap_port)
        conn.login(config.email_account, config.email_password)
        conn.select("INBOX")

        _, data = conn.search(None, "UNSEEN")
        uid_list = data[0].split()
        if not uid_list:
            conn.logout()
            return []

        uids_to_fetch = uid_list[-limit:]

        mails: list[MailItem] = []
        for uid in uids_to_fetch:
            uid_str = uid.decode()
            if uid_str in self._seen_uids:
                continue

            _, msg_data = conn.fetch(uid, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject_raw = msg.get("Subject", "(无主题)")
            subject = _decode_header_value(subject_raw)

            sender_raw = msg.get("From", "unknown")
            sender = _decode_header_value(sender_raw)

            date_raw = msg.get("Date", "")
            date = _parse_date(date_raw)

            body = _extract_body(msg)

            # 截断过长正文，保留前 3000 字给模型判断
            body = body[:3000]

            mail = MailItem(
                uid=uid_str,
                subject=subject,
                sender=sender,
                date=date,
                body_text=body,
            )
            mails.append(mail)
            self._seen_uids.add(uid_str)

        conn.logout()
        return mails
