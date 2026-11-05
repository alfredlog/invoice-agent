import os
import csv
import re
from datetime import datetime
from dotenv import load_dotenv

from email_client import EmailClient
from pdf_utils import extract_text
from classifier import InvoiceClassifier
from models import parse_invoice, review_reasons

load_dotenv()

LOG_FIELDS = [
    "status", "pruefgruende", "datei", "absender", "betreff", "aussteller",
    "rechnungsnummer", "datum", "netto", "mwst", "brutto", "waehrung",
    "extraktion", "ocr_konfidenz", "verarbeitet_am",
]


def safe_filename(text: str, max_len: int = 60) -> str:
    """Macht einen String dateisystemtauglich (keine Sonderzeichen, keine Leerzeichen)."""
    text = re.sub(r"[^\w\-]", "_", text or "unbekannt")
    return text.strip("_")[:max_len] or "unbekannt"


def save_pdf(folder: str, filename: str, content: bytes) -> str:
    """Speichert das PDF und hängt _2, _3 … an, statt eine Datei zu überschreiben."""
    base, ext = os.path.splitext(filename)
    path, n = os.path.join(folder, filename), 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{base}_{n}{ext}")
        n += 1
    with open(path, "wb") as f:
        f.write(content)
    return os.path.basename(path)


def main():
    imap_host = os.getenv("IMAP_HOST")
    imap_port = int(os.getenv("IMAP_PORT", "993"))
    imap_user = os.getenv("IMAP_USER")
    imap_password = os.getenv("IMAP_PASSWORD")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    search_days = int(os.getenv("SEARCH_DAYS", "30"))
    output_folder = os.getenv("OUTPUT_FOLDER", "./rechnungen")
    review_folder = os.getenv("REVIEW_FOLDER", "./pruefen")
    log_file = os.getenv("LOG_FILE", "./invoices_log.csv")

    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(review_folder, exist_ok=True)

    print(f"Verbinde mit {imap_host} als {imap_user} ...")
    client = EmailClient(imap_host, imap_port, imap_user, imap_password).connect()

    print(f"Suche Mails der letzten {search_days} Tage mit PDF-Anhang ...")
    emails = client.fetch_recent_with_pdf(days=search_days)
    print(f"{len(emails)} Mail(s) mit PDF-Anhang gefunden.")

    classifier = InvoiceClassifier(api_key=api_key)
    rows = []

    for msg in emails:
        for att in msg.attachments:
            extraction = extract_text(att.content)
            reasons = [extraction.error] if extraction.error else []
            inv = None

            if not reasons:
                raw, error = classifier.classify(extraction.text)
                if error:
                    reasons.append(error)
                else:
                    inv, error = parse_invoice(raw)
                    if error:
                        reasons.append(error)

            if inv is not None and not inv.is_invoice:
                continue  # sicher keine Rechnung -> ignorieren

            if inv is not None:
                reasons += review_reasons(inv, extraction.ocr_confidence)

            status = "pruefen" if reasons else "ok"
            folder = review_folder if reasons else output_folder

            date_part = (inv.invoice_date.isoformat() if inv and inv.invoice_date
                         else msg.date.strftime("%Y-%m-%d"))
            vendor_part = safe_filename((inv.vendor if inv else None) or msg.sender)
            number_part = safe_filename((inv.invoice_number if inv else None) or "ohne_nummer")
            filename = save_pdf(folder, f"{date_part}_{vendor_part}_{number_part}.pdf", att.content)

            label = "Rechnung gespeichert" if status == "ok" else "ZUR PRÜFUNG"
            print(f"  -> {label}: {filename}" + (f" ({'; '.join(reasons)})" if reasons else ""))

            rows.append({
                "status": status,
                "pruefgruende": "; ".join(reasons),
                "datei": filename,
                "absender": msg.sender,
                "betreff": msg.subject,
                "aussteller": inv.vendor if inv else None,
                "rechnungsnummer": inv.invoice_number if inv else None,
                "datum": inv.invoice_date if inv else None,
                "netto": inv.net_amount if inv else None,
                "mwst": inv.vat_amount if inv else None,
                "brutto": inv.gross_amount if inv else None,
                "waehrung": inv.currency if inv else None,
                "extraktion": extraction.method,
                "ocr_konfidenz": extraction.ocr_confidence,
                "verarbeitet_am": datetime.now().isoformat(timespec="seconds"),
            })

    # Log schreiben (Nachvollziehbarkeit für spätere Prüfung / Buchhaltung)
    if rows:
        write_header = not os.path.exists(log_file)
        with open(log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerows(rows)

    ok = sum(r["status"] == "ok" for r in rows)
    print(f"\nFertig. {ok} Rechnung(en) in '{output_folder}', "
          f"{len(rows) - ok} zur Prüfung in '{review_folder}' (Log: '{log_file}').")

    client.close()


if __name__ == "__main__":
    main()
