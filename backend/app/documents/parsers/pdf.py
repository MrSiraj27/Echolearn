import logging
import time

import pdfplumber
from pdfminer.pdfdocument import PDFEncryptionError

from app.documents.parsers.tables import rows_to_table_block
from app.documents.parsers.types import DocumentParseError, ParsedPage
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
# OCR costs seconds per page on a fast CPU and far more on Render's 0.1-vCPU free tier, so a
# long scanned PDF could otherwise hold the single parse slot (and sit on "processing") for
# an hour or more. Once the budget is spent the remaining pages are kept without OCR text,
# so the document still becomes usable with whatever was read.
OCR_TIME_BUDGET_SECONDS = 240


def _root_cause(exc: BaseException) -> BaseException:
    """pdfplumber wraps pdfminer's exceptions in PdfminerException(original)."""
    if exc.args and isinstance(exc.args[0], BaseException):
        return exc.args[0]
    return exc.__cause__ or exc


def parse_pdf(file_path: str) -> list[ParsedPage]:
    try:
        return _parse_pdf(file_path)
    except DocumentParseError:
        raise
    except Exception as exc:
        if isinstance(_root_cause(exc), PDFEncryptionError):
            raise DocumentParseError(
                "This PDF is password-protected. Remove the password (for example, print it to a new PDF) and upload it again."
            ) from exc
        logger.warning("Could not open PDF %s: %s", file_path, _root_cause(exc))
        raise DocumentParseError(
            "This PDF looks damaged or isn't a real PDF, so we couldn't open it. Try re-saving or exporting it again."
        ) from exc


def _parse_pdf(file_path: str) -> list[ParsedPage]:
    pages: list[ParsedPage] = []

    with pdfplumber.open(file_path) as pdf:
        if not pdf.pages:
            raise DocumentParseError("This PDF has no pages.")
        texts = [(page.extract_text() or "").strip() for page in pdf.pages]
        sparse = [i for i, text in enumerate(texts) if len(text) < MIN_TEXT_LENGTH_BEFORE_OCR]
        is_scanned = bool(texts) and len(sparse) / len(texts) >= SCANNED_PAGE_RATIO

        ocr_started = time.monotonic()
        ocr_skipped = 0

        for i, page in enumerate(pdf.pages):
            text = texts[i]

            if is_scanned and i in sparse and time.monotonic() - ocr_started > OCR_TIME_BUDGET_SECONDS:
                ocr_skipped += 1
            elif is_scanned and i in sparse:
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
            page.flush_cache()

        if ocr_skipped:
            logger.warning("OCR time budget hit for %s: %d page(s) left unread", file_path, ocr_skipped)

    return pages
