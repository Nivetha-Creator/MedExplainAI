import io
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
from streamlit.testing.v1 import AppTest

from backend.chatbot import answer_question
from backend.report_analyzer import extract_lab_results, summarize_lab_results


ROOT = Path(__file__).resolve().parent.parent


class SummaryTests(unittest.TestCase):
    def test_counts_use_only_stored_statuses(self):
        rows = [
            {"status": "Within the reported range"},
            {"status": "Below the reported range"},
            {"status": "Above the reported range"},
            {"status": "Below the reported lower limit"},
            {"status": "Above the reported upper limit"},
            {"status": "Not above the reported upper limit"},
            {"status": "No reference range was reported on this line"},
        ]
        summary = summarize_lab_results(rows)
        self.assertEqual(summary["total"], 7)
        self.assertEqual(summary["within"], 1)
        self.assertEqual(summary["below"], 2)
        self.assertEqual(summary["above"], 2)
        self.assertEqual(summary["not_classified"], 2)

    def test_empty_and_invalid_inputs_are_zero(self):
        empty = summarize_lab_results([])
        self.assertEqual(empty, {
            "total": 0,
            "within": 0,
            "below": 0,
            "above": 0,
            "not_classified": 0,
        })
        self.assertEqual(summarize_lab_results(None)["total"], 0)
        self.assertEqual(summarize_lab_results("not rows")["total"], 0)

    def test_real_parser_rows_match_the_summary(self):
        rows = extract_lab_results("\n".join([
            "Hemoglobin 13.5 g/dL 12.0 - 16.0",
            "Glucose 110 mg/dL 70 - 99",
            "Potassium 4.2 mmol/L",
        ]))
        summary = summarize_lab_results(rows)
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["within"], 1)
        self.assertEqual(summary["above"], 1)
        self.assertEqual(summary["below"], 0)
        self.assertEqual(summary["not_classified"], 1)


class PrivacyTests(unittest.TestCase):
    def test_failed_request_does_not_log_the_report(self):
        class FakeClient:
            def __init__(self, api_key):
                self.models = self

            def generate_content(self, model, contents):
                raise RuntimeError("service unavailable")

        marker = "UNIQUE_REPORT_MARKER"
        with patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-not-a-real-key"}):
            with patch("backend.chatbot.genai.Client", FakeClient):
                with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                    result = answer_question(
                        "Explain my report",
                        report_text=marker,
                    )
        printed = stdout.getvalue()
        self.assertNotIn(marker, printed)
        self.assertNotIn(marker, result["answer"])
        self.assertNotIn("unit-test-not-a-real-key", printed)
        self.assertNotIn("unit-test-not-a-real-key", result["answer"])


class InterfaceTests(unittest.TestCase):
    def test_suggested_questions_match_the_requested_set(self):
        source = (ROOT / "frontend" / "app.py").read_text(encoding="utf-8")
        expected = [
            "Explain my report in simple words.",
            "What does haemoglobin mean?",
            "Which results are outside their reference ranges?",
            "What does glucose measure?",
            "Explain my creatinine result.",
        ]
        for question in expected:
            self.assertIn(question, source)

    def test_every_page_loads_and_the_empty_dashboard_is_zero(self):
        app = AppTest.from_file(str(ROOT / "frontend" / "app.py"), default_timeout=30)
        app.run()
        self.assertEqual(len(app.exception), 0)

        for name in ("Home", "My Medical Report", "Ask a Question", "About"):
            app.sidebar.radio[0].set_value(name).run()
            self.assertEqual(len(app.exception), 0, app.exception)

        app.sidebar.radio[0].set_value("Home").run()
        home_text = " ".join(item.value for item in app.markdown)
        self.assertIn("Medical safety", home_text)
        self.assertIn("MedExplain AI", home_text)

        app.sidebar.radio[0].set_value("My Medical Report").run()
        metrics = {item.label: str(item.value) for item in app.metric}
        self.assertEqual(metrics["Detected tests"], "0")
        self.assertEqual(metrics["Within range"], "0")
        self.assertEqual(metrics["Below range"], "0")
        self.assertEqual(metrics["Above range"], "0")
        self.assertFalse(app.exception)

        app.sidebar.radio[0].set_value("About").run()
        about_text = " ".join(item.value for item in app.markdown)
        self.assertIn("Privacy and safety", about_text)
        self.assertIn("not a medical diagnosis", about_text.casefold())

    def test_populated_dashboard_counts_extracted_rows(self):
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), "Hemoglobin 13.5 g/dL 12.0 - 16.0", fontsize=14)
        page.insert_text((72, 100), "Glucose 110 mg/dL 70 - 99", fontsize=14)
        pdf_bytes = document.tobytes()
        document.close()

        app = AppTest.from_file(str(ROOT / "frontend" / "app.py"), default_timeout=30)
        app.run()
        app.sidebar.radio[0].set_value("My Medical Report").run()
        app.file_uploader[0].set_value(
            ("report.pdf", pdf_bytes, "application/pdf")
        ).run()
        extract = next(
            button for button in app.button
            if button.label == "Extract and Analyze Report"
        )
        extract.click().run()
        self.assertEqual(len(app.exception), 0, app.exception)

        metrics = {item.label: str(item.value) for item in app.metric}
        self.assertEqual(metrics["Detected tests"], "2")
        self.assertEqual(metrics["Within range"], "1")
        self.assertEqual(metrics["Above range"], "1")
        self.assertEqual(metrics["Below range"], "0")
        page_text = " ".join(item.value for item in app.markdown)
        self.assertIn("Manual review", page_text)
        self.assertIn("not a diagnosis", page_text.casefold())


if __name__ == "__main__":
    unittest.main()
