import io
from dataclasses import dataclass

import pdfplumber
import pymupdf
import pytesseract

# Unter so vielen Zeichen pro Seite gilt eine Seite als "ohne Textebene" (z. B. Scan).
MIN_CHARS_PER_PAGE = 30
# 300 DPI ist der übliche Richtwert für gute OCR-Qualität.
OCR_DPI = 300


@dataclass
class ExtractionResult:
    text: str
    method: str          # "text" = Textebene, "ocr" = Texterkennung, "fehler"
    ocr_confidence: float | None = None  # 0–100, nur bei OCR
    error: str | None = None


def _extract_text_layer(pdf_bytes: bytes) -> list[str]:
    """Liest die eingebettete Textebene jeder Seite (nur bei nativen PDFs vorhanden)."""
    pages = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return pages


def _ocr_page(page: pymupdf.Page) -> tuple[str, list[float]]:
    """Rendert eine Seite als Bild und lässt Tesseract den Text erkennen."""
    pix = page.get_pixmap(dpi=OCR_DPI, colorspace=pymupdf.csGRAY)
    image = pix.pil_image()
    data = pytesseract.image_to_data(
        image, lang="deu+eng", output_type=pytesseract.Output.DICT
    )
    lines: dict[tuple, list[str]] = {}
    confidences = []
    for i, word in enumerate(data["text"]):
        conf = float(data["conf"][i])
        if not word.strip() or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(word)
        confidences.append(conf)
    text = "\n".join(" ".join(words) for words in lines.values())
    return text, confidences


def extract_text(pdf_bytes: bytes, max_chars: int = 20000) -> ExtractionResult:
    try:
        pages = _extract_text_layer(pdf_bytes)
    except Exception as e:
        return ExtractionResult(text="", method="fehler", error=f"PDF nicht lesbar: {e}")

    needs_ocr = [len(p.strip()) < MIN_CHARS_PER_PAGE for p in pages]
    if not any(needs_ocr):
        return ExtractionResult(text="\n".join(pages)[:max_chars], method="text")

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        all_confidences = []
        for i, page_needs_ocr in enumerate(needs_ocr):
            if page_needs_ocr:
                pages[i], confidences = _ocr_page(doc[i])
                all_confidences.extend(confidences)
        doc.close()
    except Exception as e:
        return ExtractionResult(text="\n".join(pages)[:max_chars], method="fehler",
                                error=f"OCR fehlgeschlagen: {e}")

    avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
    return ExtractionResult(
        text="\n".join(pages)[:max_chars],
        method="ocr",
        ocr_confidence=round(avg_conf, 1),
    )
