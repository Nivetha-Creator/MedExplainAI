
from io import BytesIO
from pathlib import Path

import fitz
import pytesseract
from PIL import Image


def configure_tesseract():
    """Find Tesseract OCR on Windows."""
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]

    for path in possible_paths:
        if Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path
            return


def extract_report_text(file_bytes, filename=None):
    """Extract text from PDF, PNG, JPG, or JPEG files."""

    if not file_bytes:
        raise ValueError("The uploaded file is empty.")

    # Detect format from the actual file contents first.
    if file_bytes.startswith(b"%PDF-"):
        file_type = "pdf"
    elif file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        file_type = "png"
    elif file_bytes.startswith(b"\xff\xd8\xff"):
        file_type = "jpeg"
    else:
        # Fall back to the uploaded filename.
        file_type = Path(str(filename or "")).suffix.lower().lstrip(".")

    if file_type == "pdf":
        with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
            text = "\n".join(page.get_text() for page in pdf).strip()

            if text:
                return text

            # Scanned PDF: use OCR on each page.
            configure_tesseract()
            pages_text = []

            for page in pdf:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                image = Image.open(BytesIO(pix.tobytes("png")))
                pages_text.append(pytesseract.image_to_string(image))

            text = "\n".join(pages_text).strip()

            if not text:
                raise ValueError(
                    "No text could be detected in this PDF. "
                    "Try a clearer scan."
                )

            return text

    elif file_type in ("png", "jpg", "jpeg"):
        configure_tesseract()

        image = Image.open(BytesIO(file_bytes))
        text = pytesseract.image_to_string(image).strip()

        if not text:
            raise ValueError(
                "No text was detected in the image. "
                "Try a clearer image."
            )

        return text

    else:
        raise ValueError(
            f"Unsupported file format. Detected type: {file_type!r}; "
            f"filename: {filename!r}. Please upload a PDF, PNG, or JPEG."
        )
