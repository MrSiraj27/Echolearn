FROM python:3.11-slim

WORKDIR /app

# libgl1 / libglib2.0-0: required by opencv (used by RapidOCR). ffmpeg comes from the
# imageio-ffmpeg pip package, and OCR is RapidOCR (no tesseract needed).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STORAGE_PATH=/data/storage
ENV CHROMA_PATH=/data/chroma
ENV HF_HOME=/data/models
RUN mkdir -p /data/storage /data/chroma /data/models

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
