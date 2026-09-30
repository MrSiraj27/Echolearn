import logging

import pdfplumber

from app.documents.parsers.tables import rows_to_table_block
from app.documents.parsers.types import ParsedPage
from app.documents.parsers.image import ocr_image

logger = logging.getLogger(__name__)

MIN_TEXT_LENGTH_BEFORE_OCR = 20
# OCR is only worth it for a genuinely scanned PDF. Almost every normal PDF has a
# near-empty page or two (cover, blank separator), and OCR-ing those loads the OCR
# engine (~55MB+ on top of the ~360MB the embedding model already needs) for nothing —
# enough to OOM-kill the process on a 512MB host, which is what made every PDF upload
# fail. So only OCR when most pages have no text layer at all.
SCANNED_PAGE_RATIO = 0.5
OCR_RESOLUTION = 150


def parse_pdf(file_path: str) -> list[ParsedPage]:
    pages: list[ParsedPage] = []

    with pdfplumber.open(file_path) as pdf:
        texts = [(page.extract_text() or "").strip() for page in pdf.pages]
        sparse = [i for i, text in enumerate(texts) if len(text) < MIN_TEXT_LENGTH_BEFORE_OCR]
        is_scanned = bool(texts) and len(sparse) / len(texts) >= SCANNED_PAGE_RATIO

        for i, page in enumerate(pdf.pages):
            text = texts[i]

            if is_scanned and i in sparse:
                try:
                    image = page.to_image(resolution=OCR_RESOLUTION).original
                    ocr_text = ocr_image(image)
                    if ocr_text.strip():
                        text = ocr_text
                except Exception:
                    logger.exception("OCR fallback failed for PDF page %d of %s", i + 1, file_path)

            tables = []
            try:
                for idx, raw_table in enumerate(page.extract_tables() or []):
                    block = rows_to_table_block(raw_table, idx)
                    if block:
                        tables.append(block)
            except Exception:
                logger.exception("Table extraction failed for PDF page %d of %s", i + 1, file_path)

            pages.append(ParsedPage(page_number=i + 1, text=text, tables=tables))

    return pages
