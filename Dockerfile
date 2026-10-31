FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

# System packages required for OCR on Linux (Render Docker runtime).
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && tesseract --version \
    && tesseract --list-langs

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Confirm the app can locate Tesseract through PATH before the service starts.
RUN python -c "from backend.ocr import verify_tesseract; status = verify_tesseract(); assert status['available'], status['detail']; print(status['detail'])"

EXPOSE 10000

# Render injects PORT. Bind on all interfaces for the public service.
CMD ["sh", "-c", "streamlit run frontend/app.py --server.address=0.0.0.0 --server.port=${PORT:-10000} --server.headless=true --browser.gatherUsageStats=false"]
