
FROM python:3.11-slim

WORKDIR /app

# Install Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Start Streamlit
EXPOSE 10000

CMD ["sh", "-c", "streamlit run frontend/app.py --server.address=0.0.0.0 --server.port=${PORT:-10000}"]
