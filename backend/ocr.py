import shutil
import subprocess
from io import BytesIO
from pathlib import Path

import fitz
import pytesseract
from PIL import Image


class ReportReadError(ValueError):
    """The uploaded file could not be read as report text."""


# Prefer PATH and common Linux install locations used by Docker/Render.
_LINUX_TESSERACT_PATHS = (
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
)

_WINDOWS_TESSERACT_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)


def _candidate_tesseract_paths():
    """Return install candidates. PATH / Linux first; Windows only as fallback."""
    seen = set()
    ordered = []

    for candidate in (
        shutil.which("tesseract"),
        *_LINUX_TESSERACT_PATHS,
        *_WINDOWS_TESSERACT_PATHS,
    ):
        if not candidate:
            continue
        normalized = str(Path(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def configure_tesseract():
    """
    Point pytesseract at a working Tesseract binary.

    Detection uses the process PATH and standard Linux locations first so
    Docker and Render deployments do not depend on a Windows path.
    """
    current = getattr(pytesseract.pytesseract, "tesseract_cmd", None)
    if current and current not in ("tesseract", "tesseract.exe"):
        current_path = Path(current)
        if current_path.exists():
            return str(current_path)

    for candidate in _candidate_tesseract_paths():
        path = Path(candidate)
        if not path.exists():
            continue
        pytesseract.pytesseract.tesseract_cmd = str(path)
        return str(path)

    raise ReportReadError(
        "Tesseract OCR is not installed or could not be found. "
        "A PDF that already contains text can still be read. "
        "Scanned PDFs and images need Tesseract on the system PATH."
    )


def verify_tesseract():
    """
    Confirm Tesseract can be found and started.

    Returns a dict with available, path, version, and detail fields.
    Never includes secrets or report contents.
    """
    try:
        path = configure_tesseract()
    except ReportReadError as error:
        return {
            "available": False,
            "path": "",
            "version": "",
            "detail": str(error),
        }

    try:
        version = str(pytesseract.get_tesseract_version())
        return {
            "available": True,
            "path": path,
            "version": version,
            "detail": f"Tesseract {version} is available.",
        }
    except Exception:
        # Fall back to a direct --version call if the helper fails.
        try:
            completed = subprocess.run(
                [path, "--version"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            first_line = (completed.stdout or completed.stderr or "").splitlines()
            version = first_line[0].strip() if first_line else "unknown"
            return {
                "available": True,
                "path": path,
                "version": version,
                "detail": f"Tesseract is available at {path}.",
            }
        except Exception as error:
            return {
                "available": False,
                "path": path,
                "version": "",
                "detail": (
                    "Tesseract was found but could not be started. "
                    f"Error type: {type(error).__name__}."
                ),
            }


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
        # Ensure the command path is set before every OCR call.
        configure_tesseract()
        return pytesseract.image_to_string(
            prepared,
            config="--psm 6",
        ).strip()
    except pytesseract.TesseractNotFoundError as error:
        raise ReportReadError(
            "Tesseract OCR is not installed or could not be found. "
            "On Render, rebuild the Docker image so tesseract-ocr is installed."
        ) from error
    except ReportReadError:
        raise
    except Exception as error:
        raise ReportReadError(
            "The report image could not be read. Try a clearer PNG or JPEG."
        ) from error
