import shutil
from io import BytesIO
from pathlib import Path

import fitz
import pytesseract
from PIL import Image


class ReportReadError(ValueError):
    """The uploaded file could not be read as report text."""


def configure_tesseract():
    """Find a local Tesseract binary, including a typical Windows install."""
    current = getattr(pytesseract.pytesseract, "tesseract_cmd", None)
    if current and current != "tesseract" and Path(current).exists():
        return str(current)

    candidates = [
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return str(candidate)

    raise ReportReadError(
        "Tesseract OCR is not installed or could not be found. "
        "A PDF that already contains text can still be read. "
        "Scanned PDFs and images need Tesseract on the system PATH."
    )


def extract_report_text(file_bytes, filename=None):
    """Extract text from PDF, PNG, JPG, or JPEG files."""

    if not file_bytes:
        raise ReportReadError("The uploaded file is empty.")

    if file_bytes.startswith(b"%PDF-"):
        file_type = "pdf"
    elif file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        file_type = "png"
    elif file_bytes.startswith(b"\xff\xd8\xff"):
        file_type = "jpeg"
    else:
        file_type = Path(str(filename or "")).suffix.lower().lstrip(".")

    if file_type == "pdf":
        return _extract_pdf(file_bytes)

    if file_type in ("png", "jpg", "jpeg"):
        return _extract_image(file_bytes)

    raise ReportReadError(
        f"Unsupported file format. Detected type: {file_type!r}; "
        f"filename: {filename!r}. Please upload a PDF, PNG, or JPEG."
    )


def _extract_pdf(file_bytes):
    try:
        pdf = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as error:
        raise ReportReadError(
            "This PDF could not be opened. It may be damaged or "
            "password-protected."
        ) from error

    with pdf:
        if pdf.is_encrypted:
            raise ReportReadError(
                "This PDF is password-protected. Upload an unprotected copy."
            )
        if pdf.page_count < 1:
            raise ReportReadError("This PDF has no pages.")

        try:
            text = "\n".join(page.get_text() for page in pdf).strip()
        except Exception as error:
            raise ReportReadError(
                "Text could not be read from this PDF."
            ) from error

        if text:
            return text

        configure_tesseract()
        pages_text = []
        for page in pdf:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            image = Image.open(BytesIO(pixmap.tobytes("png")))
            pages_text.append(_read_image_text(image))

        text = "\n".join(part for part in pages_text if part).strip()
        if not text:
            raise ReportReadError(
                "No text could be detected in this PDF. Try a clearer scan."
            )
        return text


def _extract_image(file_bytes):
    configure_tesseract()
    try:
        image = Image.open(BytesIO(file_bytes))
        image.load()
    except Exception as error:
        raise ReportReadError(
            "This image could not be opened. Upload a PNG or JPEG report."
        ) from error

    text = _read_image_text(image)
    if not text:
        raise ReportReadError(
            "No text was detected in the image. Try a clearer image."
        )
    return text


def _prepare_image(image):
    image = image.convert("L")
    if image.width < 1400:
        scale = max(2, round(1400 / max(image.width, 1)))
        image = image.resize(
            (image.width * scale, image.height * scale),
            Image.Resampling.LANCZOS,
        )
    return image


def _read_image_text(image):
    prepared = _prepare_image(image)
    try:
        return pytesseract.image_to_string(
            prepared,
            config="--psm 6",
        ).strip()
    except pytesseract.TesseractNotFoundError as error:
        raise ReportReadError(
            "Tesseract OCR is not installed or could not be found."
        ) from error
    except ReportReadError:
        raise
    except Exception as error:
        raise ReportReadError(
            "The report image could not be read. Try a clearer PNG or JPEG."
        ) from error
