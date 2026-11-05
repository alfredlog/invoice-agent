# Invoice Agent – Prototyp

Ein einfacher AI-Agent, der ein E-Mail-Postfach durchsucht, Rechnungen erkennt,
automatisch herunterlädt und in einem Ordner speichert. Gebaut für die
Vorab-Aufgabe von Patch & Sparks.

## Architektur

```
E-Mail-Postfach (IMAP)
        │
        ▼
1) Vorfilter: Mails der letzten N Tage MIT PDF-Anhang   (email_client.py)
        │
        ▼
2) Text aus PDF extrahieren: Textebene, sonst OCR        (pdf_utils.py)
        │
        ▼
3) Claude API: "Ist das eine Rechnung? Extrahiere Felder" (classifier.py)
        │
        ▼
4) Schema prüfen (Pydantic) + Geschäftsregeln             (models.py)
        │
        ├── alles ok      → ./rechnungen  (Status "ok")
        └── Auffälligkeit → ./pruefen     (Status "pruefen" + Gründe)
        │
        ▼
5) CSV-Log mit Status, Prüfgründen und OCR-Konfidenz      (main.py)
```

Gescannte PDFs werden automatisch per OCR (Tesseract, Deutsch + Englisch)
gelesen. Eine Rechnung landet zur manuellen Prüfung, wenn z. B. die
Rechnungsnummer fehlt, Netto + MwSt. nicht den Bruttobetrag ergibt, das Datum
in der Zukunft liegt oder die OCR-Konfidenz unter 80 % liegt. Fehler (API
nicht erreichbar, ungültige KI-Antwort) gehen ebenfalls zur Prüfung, statt
still verworfen zu werden.

## Setup

Tesseract muss als Programm installiert sein:

```bash
sudo apt install tesseract-ocr tesseract-ocr-deu   # Linux (Debian/Ubuntu)
brew install tesseract tesseract-lang              # macOS
```

```bash
pip install -r requirements.txt
cp .env.example .env
# .env ausfüllen: IMAP-Zugang + ANTHROPIC_API_KEY
python main.py
```

**Gmail-Nutzer:** IMAP muss in den Gmail-Einstellungen aktiviert sein, und
statt des normalen Passworts wird ein "App-Passwort" benötigt
(Google-Konto -> Sicherheit -> App-Passwörter; setzt 2FA voraus).

