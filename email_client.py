
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class EmailAttachment:
    filename: str
    content: bytes


@dataclass
class EmailMessage:
    subject: str
    sender: str
    date: datetime
    attachments: list = field(default_factory=list)


def _decode(value: str) -> str:
    """Decodiert MIME-encodierte Header (z.B. '=?UTF-8?B?...?=')."""
    parts = decode_header(value)
    result = ""
    for text, enc in parts:
        if isinstance(text, bytes):
            result += text.decode(enc or "utf-8", errors="ignore")
        else:
            result += text
    return result


class EmailClient:
    def __init__(self, host: str, port: int, user: str, password: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self._conn = None

    def connect(self):
        self._conn = imaplib.IMAP4_SSL(self.host, self.port)
        self._conn.login(self.user, self.password)
        return self

    def close(self):
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn.logout()

    def fetch_recent_with_pdf(self, days: int = 30, mailbox: str = "INBOX") -> list[EmailMessage]:
        self._conn.select(mailbox)
        since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
        status, data = self._conn.search(None, f'(SINCE "{since_date}")')
        if status != "OK":
            return []

        results = []
        for num in data[0].split():
            # BODY.PEEK[] lädt die Mail, ohne sie als "gelesen" zu markieren
            status, msg_data = self._conn.fetch(num, "(BODY.PEEK[])")
            if status != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])

            attachments = []
            for part in msg.walk():
                if part.get_content_disposition() == "attachment":
                    filename = part.get_filename()
                    if filename and filename.lower().endswith(".pdf"):
                        filename = _decode(filename)
                        content = part.get_payload(decode=True)
                        attachments.append(EmailAttachment(filename, content))

            if not attachments:
                continue  # Vorfilter: keine PDF-Anhänge -> überspringen

            subject = _decode(msg.get("Subject", ""))
            sender = _decode(msg.get("From", ""))
            date_str = msg.get("Date", "")
            try:
                date = email.utils.parsedate_to_datetime(date_str)
            except Exception:
                date = datetime.now()

            results.append(EmailMessage(subject, sender, date, attachments))

        return results
