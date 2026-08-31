import logging

import pdfplumber

from app.documents.parsers.tables import rows_to_table_block
from app.documents.parsers.types import ParsedPage
from app.documents.parsers.image import ocr_image

logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH_BEFORE_OCR = 20


def parse_pdf(file_path: str) -> list[ParsedPage]:
    pages: list[ParsedPage] = []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()

            if len(text) < MIN_TEXT_LENGTH_BEFORE_OCR:
                # Likely a scanned page — rasterize and OCR it.
                try:
                    image = page.to_image(resolution=200).original
                    ocr_text = ocr_image(image)
                    if ocr_text.strip():
                        text = ocr_text
                except Exception:
                    logger.exception("OCR fallback failed for PDF page %d of %s", i, file_path)

            tables = []
            try:
                for idx, raw_table in enumerate(page.extract_tables() or []):
                    block = rows_to_table_block(raw_table, idx)
                    if block:
                        tables.append(block)
            except Exception:
                logger.exception("Table extraction failed for PDF page %d of %s", i, file_path)

            pages.append(ParsedPage(page_number=i, text=text, tables=tables))

    return pages
