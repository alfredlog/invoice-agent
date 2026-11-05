import json
import time
from anthropic import Anthropic, APIStatusError, APIConnectionError

SYSTEM_PROMPT = """Du bist ein Assistent, der PDF-Textinhalte analysiert und \
ausschließlich mit einem validen JSON-Objekt antwortet, ohne weiteren Text. \
Der Text kann aus einer Texterkennung (OCR) stammen und Erkennungsfehler enthalten.
Format:
{
  "is_invoice": true|false,
  "vendor": "Name des Ausstellers oder null",
  "invoice_number": "Rechnungsnummer oder null",
  "invoice_date": "Rechnungsdatum im Format YYYY-MM-DD oder null",
  "net_amount": Nettobetrag als Zahl mit Punkt als Dezimaltrennzeichen (z. B. 1234.50) oder null,
  "vat_amount": MwSt.-Betrag als Zahl oder null,
  "gross_amount": Bruttobetrag (Gesamtbetrag) als Zahl oder null,
  "currency": "ISO-Währungscode wie EUR oder null"
}
Regeln:
- Übernimm nur Werte, die im Text stehen. Rate nichts; wenn ein Wert fehlt oder unleserlich ist: null.
- Deutsche Beträge wie "1.234,50 €" werden zu 1234.50.
Antworte NUR mit dem JSON-Objekt, keine Erklärung, keine Markdown-Codeblöcke."""


class InvoiceClassifier:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def classify(self, pdf_text: str, max_retries: int = 5) -> tuple[dict | None, str | None]:
        """Gibt (Rohdaten, Fehler) zurück. Bei Fehler sind die Rohdaten None."""
        response = None
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=400,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": pdf_text or "(leerer Text)"}],
                )
                break
            except (APIStatusError, APIConnectionError) as e:
                if attempt == max_retries - 1:
                    return None, f"Claude API nicht erreichbar: {e}"
                wait = 2 ** attempt
                print(f"    [Hinweis] API-Fehler, neuer Versuch in {wait}s "
                      f"({attempt + 1}/{max_retries}) ...")
                time.sleep(wait)

        raw = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned), None
        except json.JSONDecodeError:
            return None, "Antwort der KI ist kein gültiges JSON"
