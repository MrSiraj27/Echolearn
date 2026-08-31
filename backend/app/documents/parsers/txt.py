from app.documents.parsers.types import ParsedPage


def parse_txt(file_path: str) -> list[ParsedPage]:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return [ParsedPage(page_number=1, text=text)]
