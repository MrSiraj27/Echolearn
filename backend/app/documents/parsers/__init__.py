from app.documents.parsers.audio import parse_audio, parse_video
from app.documents.parsers.csv import parse_csv
from app.documents.parsers.docx import parse_docx
from app.documents.parsers.image import parse_image
from app.documents.parsers.pdf import parse_pdf
from app.documents.parsers.pptx import parse_pptx
from app.documents.parsers.txt import parse_txt
from app.documents.parsers.types import ParsedPage

EXTENSION_DISPATCH = {
    "pdf": parse_pdf,
    "docx": parse_docx,
    "pptx": parse_pptx,
    "txt": parse_txt,
    "csv": parse_csv,
    "png": parse_image,
    "jpg": parse_image,
    "jpeg": parse_image,
    "mp3": parse_audio,
    "wav": parse_audio,
    "m4a": parse_audio,
    "mp4": parse_video,
    "mov": parse_video,
}

AUDIO_VIDEO_EXTENSIONS = {"mp3", "wav", "m4a", "mp4", "mov"}
VIDEO_EXTENSIONS = {"mp4", "mov"}

SUPPORTED_EXTENSIONS = set(EXTENSION_DISPATCH.keys())


class UnsupportedFileTypeError(ValueError):
    pass


def parse_file(file_path: str, extension: str) -> list[ParsedPage]:
    parser = EXTENSION_DISPATCH.get(extension.lower())
    if parser is None:
        raise UnsupportedFileTypeError(f"Unsupported file type: {extension}")
    return parser(file_path)


__all__ = [
    "parse_file",
    "ParsedPage",
    "SUPPORTED_EXTENSIONS",
    "AUDIO_VIDEO_EXTENSIONS",
    "VIDEO_EXTENSIONS",
    "UnsupportedFileTypeError",
]
