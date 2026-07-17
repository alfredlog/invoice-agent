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
2) Text aus PDF extrahieren                              (pdf_utils.py)
        │
        ▼
3) Claude API: "Ist das eine Rechnung? Extrahiere Felder" (classifier.py)
        │
        ▼
4) Wenn ja: PDF speichern + CSV-Log schreiben             (main.py)
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# .env ausfüllen: IMAP-Zugang + ANTHROPIC_API_KEY
python main.py
```

**Gmail-Nutzer:** IMAP muss in den Gmail-Einstellungen aktiviert sein, und
statt des normalen Passworts wird ein "App-Passwort" benötigt
(Google-Konto -> Sicherheit -> App-Passwörter; setzt 2FA voraus).

