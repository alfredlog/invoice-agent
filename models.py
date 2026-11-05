from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, ValidationError, field_validator

# Unterhalb dieser OCR-Konfidenz (0–100) wird eine Rechnung immer manuell geprüft.
MIN_OCR_CONFIDENCE = 80.0
# Erlaubte Rundungsdifferenz bei Netto + MwSt. = Brutto.
TOLERANCE = Decimal("0.02")


class InvoiceData(BaseModel):
    is_invoice: bool
    vendor: str | None = None
    invoice_number: str | None = None
    invoice_date: date | None = None
    net_amount: Decimal | None = Field(default=None, ge=0)
    vat_amount: Decimal | None = Field(default=None, ge=0)
    gross_amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


def parse_invoice(raw: dict) -> tuple[InvoiceData | None, str | None]:
    """Prüft die KI-Antwort gegen das Schema. Gibt (Daten, Fehler) zurück."""
    try:
        return InvoiceData.model_validate(raw), None
    except ValidationError as e:
        fields = ", ".join(str(err["loc"][0]) for err in e.errors())
        return None, f"Ungültige Felder: {fields}"


def review_reasons(inv: InvoiceData, ocr_confidence: float | None) -> list[str]:
    """Geschäftsregeln: Liefert alle Gründe, warum ein Mensch die Rechnung prüfen soll."""
    reasons = []
    if not inv.invoice_number:
        reasons.append("Rechnungsnummer fehlt")
    if inv.gross_amount is None:
        reasons.append("Bruttobetrag fehlt")
    if inv.invoice_date is None:
        reasons.append("Rechnungsdatum fehlt")
    elif inv.invoice_date > date.today():
        reasons.append("Rechnungsdatum liegt in der Zukunft")
    if None not in (inv.net_amount, inv.vat_amount, inv.gross_amount):
        if abs(inv.net_amount + inv.vat_amount - inv.gross_amount) > TOLERANCE:
            reasons.append("Netto + MwSt. ergibt nicht den Bruttobetrag")
    if ocr_confidence is not None and ocr_confidence < MIN_OCR_CONFIDENCE:
        reasons.append(f"OCR-Konfidenz niedrig ({ocr_confidence})")
    return reasons
