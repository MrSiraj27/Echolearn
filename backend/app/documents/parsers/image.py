import pytesseract
from PIL import Image

from app.core.config import settings
from app.documents.parsers.types import ParsedPage

if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


def ocr_image(image: Image.Image) -> str:
    return pytesseract.image_to_string(image)


def parse_image(file_path: str) -> list[ParsedPage]:
    with Image.open(file_path) as image:
        text = ocr_image(image)
    return [ParsedPage(page_number=1, text=text)]
