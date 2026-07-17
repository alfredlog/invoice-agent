
import json
import time
from anthropic import Anthropic, APIStatusError, APIConnectionError

SYSTEM_PROMPT = """Du bist ein Assistent, der PDF-Textinhalte analysiert und \
ausschließlich mit einem validen JSON-Objekt antwortet, ohne weiteren Text. \
Format:
{
  "is_invoice": true|false,
  "vendor": "Name des Ausstellers oder null",
  "invoice_number": "Rechnungsnummer oder null",
  "amount": "Betrag inkl. Währung als String oder null",
  "date": "Rechnungsdatum im Format YYYY-MM-DD oder null"
}
Antworte NUR mit dem JSON-Objekt, keine Erklärung, keine Markdown-Codeblöcke."""


class InvoiceClassifier:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def classify(self, pdf_text: str, max_retries: int = 5) -> dict:
        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=300,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": pdf_text or "(leerer Text)"}],
                )
                break
            except (APIStatusError, APIConnectionError) as e:
                last_error = e
                is_overloaded = getattr(e, "status_code", None) == 529
                is_last_attempt = attempt == max_retries - 1
                if is_last_attempt:
                    print(f"    [Warnung] Claude API weiterhin nicht erreichbar "
                          f"nach {max_retries} Versuchen ({e}). Überspringe diesen Anhang.")
                    return {"is_invoice": False, "vendor": None,
                            "invoice_number": None, "amount": None, "date": None,
                            "_error": str(e)}
                wait = 2 ** attempt
                reason = "Server überlastet" if is_overloaded else "Verbindungsfehler"
                print(f"    [Hinweis] {reason}, warte {wait}s und versuche es erneut "
                      f"(Versuch {attempt + 1}/{max_retries}) ...")
                time.sleep(wait)
        else:
            raise last_error

        raw = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Robustheit: falls die KI doch mal Markdown-Fences liefert
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                return {"is_invoice": False, "vendor": None,
                        "invoice_number": None, "amount": None, "date": None}