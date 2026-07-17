

import io
import pdfplumber


def extract_text(pdf_bytes: bytes, max_chars: int = 6000) -> str:
    text_parts = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
                if sum(len(t) for t in text_parts) > max_chars:
                    break
    except Exception as e:
        return f"[Fehler beim Lesen des PDFs: {e}]"

    full_text = "\n".join(text_parts)
    return full_text[:max_chars]
