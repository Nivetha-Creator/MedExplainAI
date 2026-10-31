import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import ocr


class TesseractDetectionTests(unittest.TestCase):
    def test_verify_reports_available_tesseract_on_this_host(self):
        status = ocr.verify_tesseract()
        which = shutil.which("tesseract")
        if which is None and not Path("/usr/bin/tesseract").exists():
            self.skipTest("Tesseract is not installed on this host")
        self.assertTrue(status["available"], status)
        self.assertTrue(status["path"])
        self.assertTrue(status["version"])
        self.assertNotIn("GEMINI", status["detail"].upper())

    def test_configure_prefers_path_or_linux_binary(self):
        path = ocr.configure_tesseract()
        self.assertTrue(Path(path).exists())
        self.assertFalse(path.lower().endswith("tesseract.exe"))

    def test_candidate_order_puts_path_and_linux_before_windows(self):
        with patch("backend.ocr.shutil.which", return_value="/usr/bin/tesseract"):
            candidates = ocr._candidate_tesseract_paths()
        self.assertEqual(candidates[0], "/usr/bin/tesseract")
        windows = [item for item in candidates if item.lower().endswith("tesseract.exe")]
        self.assertTrue(windows)
        self.assertGreater(candidates.index(windows[0]), 0)

    def test_missing_binary_raises_a_clear_error(self):
        import pytesseract

        original = pytesseract.pytesseract.tesseract_cmd
        try:
            pytesseract.pytesseract.tesseract_cmd = "tesseract"
            with patch("backend.ocr.shutil.which", return_value=None):
                with patch.object(Path, "exists", return_value=False):
                    with self.assertRaises(ocr.ReportReadError) as raised:
                        ocr.configure_tesseract()
        finally:
            pytesseract.pytesseract.tesseract_cmd = original
        self.assertIn("Tesseract OCR is not installed", str(raised.exception))

    def test_verify_reports_unavailable_without_raising(self):
        with patch(
            "backend.ocr.configure_tesseract",
            side_effect=ocr.ReportReadError("Tesseract OCR is not installed"),
        ):
            status = ocr.verify_tesseract()
        self.assertFalse(status["available"])
        self.assertEqual(status["path"], "")
        self.assertIn("Tesseract OCR is not installed", status["detail"])


if __name__ == "__main__":
    unittest.main()
