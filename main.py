
import os
import csv
import re
from datetime import datetime
from dotenv import load_dotenv

from email_client import EmailClient
from pdf_utils import extract_text
from classifier import InvoiceClassifier

load_dotenv()


def safe_filename(text: str, max_len: int = 60) -> str:
    """Macht einen String dateisystemtauglich (keine Sonderzeichen, keine Leerzeichen)."""
    text = re.sub(r"[^\w\-]", "_", text or "unbekannt")
    return text.strip("_")[:max_len] or "unbekannt"


def main():
    imap_host = os.getenv("IMAP_HOST")
    imap_port = int(os.getenv("IMAP_PORT", "993"))
    imap_user = os.getenv("IMAP_USER")
    imap_password = os.getenv("IMAP_PASSWORD")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    search_days = int(os.getenv("SEARCH_DAYS", "30"))
    output_folder = os.getenv("OUTPUT_FOLDER", "./rechnungen")
    log_file = os.getenv("LOG_FILE", "./invoices_log.csv")

    os.makedirs(output_folder, exist_ok=True)

    print(f"Verbinde mit {imap_host} als {imap_user} ...")
    client = EmailClient(imap_host, imap_port, imap_user, imap_password).connect()

    print(f"Suche Mails der letzten {search_days} Tage mit PDF-Anhang ...")
    emails = client.fetch_recent_with_pdf(days=search_days)
    print(f"{len(emails)} Mail(s) mit PDF-Anhang gefunden.")

    classifier = InvoiceClassifier(api_key=api_key)
    found_invoices = []

    for msg in emails:
        for att in msg.attachments:
            text = extract_text(att.content)
            result = classifier.classify(text)

            if not result.get("is_invoice"):
                continue

            date_part = result.get("date") or msg.date.strftime("%Y-%m-%d")
            vendor_part = safe_filename(result.get("vendor") or msg.sender)
            number_part = safe_filename(result.get("invoice_number") or "ohne_nummer")
            filename = f"{date_part}_{vendor_part}_{number_part}.pdf"
            filepath = os.path.join(output_folder, filename)

            with open(filepath, "wb") as f:
                f.write(att.content)

            print(f"  -> Rechnung erkannt & gespeichert: {filename}")
            found_invoices.append({
                "datei": filename,
                "absender": msg.sender,
                "betreff": msg.subject,
                "aussteller": result.get("vendor"),
                "rechnungsnummer": result.get("invoice_number"),
                "betrag": result.get("amount"),
                "datum": result.get("date"),
                "verarbeitet_am": datetime.now().isoformat(timespec="seconds"),
            })

    # Log schreiben (Nachvollziehbarkeit für spätere Prüfung / Buchhaltung)
    if found_invoices:
        write_header = not os.path.exists(log_file)
        with open(log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(found_invoices[0].keys()))
            if write_header:
                writer.writeheader()
            writer.writerows(found_invoices)

    print(f"\nFertig. {len(found_invoices)} Rechnung(en) erkannt und in "
          f"'{output_folder}' gespeichert (Log: '{log_file}').")

    client.close()


if __name__ == "__main__":
    main()
