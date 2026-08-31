from app.documents.parsers.types import TableBlock


def rows_to_table_block(rows: list[list[str | None]], table_index: int) -> TableBlock | None:
    """Convert a raw grid of cell values (first row = header) into a clean Markdown table
    string (for LLM context — models parse Markdown tables far more reliably than a raw
    text dump) plus a JSON rows-as-dicts representation for structured use."""
    cleaned = [[("" if c is None else str(c).strip()) for c in row] for row in rows]
    cleaned = [row for row in cleaned if any(cell for cell in row)]
    if len(cleaned) < 2:
        return None

    header, *body = cleaned
    ncols = len(header)
    if ncols == 0:
        return None
    header = [h or f"Column {i + 1}" for i, h in enumerate(header)]
    body = [(row + [""] * ncols)[:ncols] for row in body]

    md_lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * ncols) + " |",
    ]
    for row in body:
        md_lines.append("| " + " | ".join(cell.replace("|", "/") for cell in row) + " |")

    json_table = [dict(zip(header, row)) for row in body]
    return TableBlock(table_index=table_index, markdown_table="\n".join(md_lines), json_table=json_table)
