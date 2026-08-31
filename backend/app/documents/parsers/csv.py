import pandas as pd

from app.documents.parsers.types import ParsedPage

ROWS_PER_PAGE = 200


def parse_csv(file_path: str) -> list[ParsedPage]:
    df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
    columns = list(df.columns)

    pages: list[ParsedPage] = []
    rows = df.values.tolist()

    for i in range(0, len(rows), ROWS_PER_PAGE):
        chunk = rows[i : i + ROWS_PER_PAGE]
        lines = [", ".join(f"{col}: {val}" for col, val in zip(columns, row)) for row in chunk]
        pages.append(ParsedPage(page_number=i // ROWS_PER_PAGE + 1, text="\n".join(lines)))

    if not pages:
        pages.append(ParsedPage(page_number=1, text=""))

    return pages
