import io
import re
import unicodedata

from pypdf import PdfReader


def clean_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"[\x00-\x1F\x7F]", " ", normalized)
    normalized = re.sub(r"[\u2022\u25CF\u25AA\u25E6]", "-", normalized)
    normalized = re.sub(r"[^\S\r\n]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = [page.extract_text() or "" for page in reader.pages]
    return clean_text("\n".join(pages))
