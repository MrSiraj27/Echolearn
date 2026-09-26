from PIL import Image

from app.documents.parsers.types import ParsedPage

_engine = None

# A full-resolution phone photo (often 3000x4000px+) costs the detection model far more
# memory/CPU than a document image needs — text is still perfectly readable at this size,
# but a large image was observed to OOM-crash the whole process on Render's 512MB limit.
MAX_OCR_DIMENSION = 1600


def _load_engine():
    """Loaded once and reused — same singleton pattern as the Whisper model in
    app/documents/parsers/audio.py. Uses rapidocr-onnxruntime instead of
    pytesseract/system tesseract: Render's native Python runtime (render.yaml's
    `runtime: python`) has no apt-get/root access, so a system tesseract binary was
    never actually installable in production — this ships its own small (~16MB)
    ONNX models directly in the pip package, no external binary needed, and reuses
    the onnxruntime dependency fastembed already pulls in."""
    global _engine
    if _engine is not None:
        return _engine

    from rapidocr_onnxruntime import RapidOCR

    # onnxruntime defaults to auto-detecting CPU count for its thread pool, which on a
    # throttled container (Render's free tier is quota-limited to 0.1 CPU but still
    # reports the host's full core count via os.cpu_count()) causes severe thread
    # contention — far more threads spawned than the container can actually run
    # concurrently, making inference dramatically slower than a single thread would be
    # (observed as uploads never finishing in practice). Pinning to 1 thread each avoids
    # this well-known container/CPU-quota mismatch.
    _engine = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
    return _engine


def _to_ocr_input(image: Image.Image):
    import numpy as np

    if max(image.size) > MAX_OCR_DIMENSION:
        scale = MAX_OCR_DIMENSION / max(image.size)
        new_size = (round(image.width * scale), round(image.height * scale))
        image = image.resize(new_size, Image.LANCZOS)
    return np.array(image.convert("RGB"))


def ocr_image(image: str | Image.Image) -> str:
    """Accepts either a file path (direct image upload) or an already-open PIL Image
    (the PDF OCR fallback in pdf.py rasterizes a scanned page in memory)."""
    if isinstance(image, str):
        with Image.open(image) as opened:
            ocr_input = _to_ocr_input(opened)
    else:
        ocr_input = _to_ocr_input(image)

    engine = _load_engine()
    result, _elapse = engine(ocr_input)
    if not result:
        return ""
    # Each result item is [bounding_box, text, confidence] — join the lines in
    # detection order (top-to-bottom, matching reading order for most documents).
    return "\n".join(line[1] for line in result)


def parse_image(file_path: str) -> list[ParsedPage]:
    text = ocr_image(file_path)
    return [ParsedPage(page_number=1, text=text)]
