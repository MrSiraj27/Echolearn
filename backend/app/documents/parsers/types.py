from dataclasses import dataclass, field


@dataclass
class TableBlock:
    table_index: int
    markdown_table: str
    json_table: list[dict]


@dataclass
class ParsedPage:
    page_number: int
    text: str
    tables: list[TableBlock] = field(default_factory=list)
    # Set only for audio/video transcript segments — page_number doubles as a segment
    # index for those, and start_time/end_time (seconds) drive chunk timestamp metadata.
    start_time: float | None = None
    end_time: float | None = None
