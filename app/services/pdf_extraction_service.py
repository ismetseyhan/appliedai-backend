import pdfplumber
import io
from typing import Optional


class PDFExtractionService:

    @staticmethod
    def extract_text_from_bytes(pdf_bytes: bytes, max_pages: Optional[int] = None) -> str:
        """
        Extract text from PDF using pdfplumber.
        """
        parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages_to_extract = len(pdf.pages)
            if max_pages:
                pages_to_extract = min(pages_to_extract, max_pages)

            for i in range(pages_to_extract):
                text = pdf.pages[i].extract_text()
                parts.append(text or "")  # Handle None for blank pages

        return "\n".join(parts)
