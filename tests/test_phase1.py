import io
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
from PIL import Image, ImageDraw, ImageFont

from backend.chatbot import (
    answer_question,
    prepare_model_context,
    report_context_for_model,
)
from backend.ocr import ReportReadError, extract_report_text
from backend.rag import retrieve_information
from backend.report_analyzer import extract_lab_results


ROOT = Path(__file__).resolve().parent.parent
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _by_name(results, fragment):
    fragment = fragment.casefold()
    matches = [
        item for item in results
        if fragment in item["test_name"].casefold()
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {fragment!r} result, found {results}")
    return matches[0]


class LabResultTests(unittest.TestCase):
    def test_full_range_statuses_use_only_printed_bounds(self):
        text = "\n".join([
            "Hemoglobin 13.5 g/dL 12.0 - 16.0",
            "Glucose 110 mg/dL 70-99",
            "Platelets 140 10^3/uL 150 - 450",
            "HbA1c 5.6 % (4.0-5.6)",
            "Creatinine 1.4 mg/dL",
            "0.6 – 1.3",
            "Potassium 4.2 mmol/L",
        ])
        results = extract_lab_results(text)

        hemoglobin = _by_name(results, "hemoglobin")
        self.assertEqual(hemoglobin["value"], 13.5)
        self.assertEqual(hemoglobin["unit"].casefold(), "g/dl")
        self.assertEqual(hemoglobin["reference_low"], 12.0)
        self.assertEqual(hemoglobin["reference_high"], 16.0)
        self.assertEqual(hemoglobin["status"], "Within the reported range")
        self.assertIn("not a diagnosis", hemoglobin["explanation"].casefold())
        self.assertNotIn("you have", hemoglobin["explanation"].casefold())
        self.assertNotIn("17", hemoglobin["explanation"])

        glucose = _by_name(results, "glucose")
        self.assertEqual(glucose["status"], "Above the reported range")
        self.assertEqual(glucose["reference_text"], "70 - 99")

        platelets = _by_name(results, "platelet")
        self.assertEqual(platelets["status"], "Below the reported range")
        self.assertEqual(platelets["reference_low"], 150)

        a1c = _by_name(results, "hba1c")
        self.assertEqual(a1c["status"], "Within the reported range")
        self.assertEqual(a1c["unit"], "%")

        creatinine = _by_name(results, "creatinine")
        self.assertEqual(creatinine["value"], 1.4)
        self.assertEqual(creatinine["status"], "Above the reported range")
        self.assertEqual(creatinine["reference_text"], "0.6 - 1.3")

        potassium = _by_name(results, "potassium")
        self.assertIsNone(potassium["reference_low"])
        self.assertIsNone(potassium["reference_high"])
        self.assertEqual(potassium["reference_text"], "")
        self.assertIn("No reference range", potassium["status"])
        self.assertNotIn("Within the reported range", potassium["explanation"])

    def test_one_sided_limits_do_not_invent_the_other_bound(self):
        results = extract_lab_results("\n".join([
            "TSH 0.2 mIU/L < 4.0",
            "HDL 55 mg/dL > 40",
            "Sodium 139 mmol/L <= 145",
        ]))

        tsh = _by_name(results, "tsh")
        self.assertIsNone(tsh["reference_low"])
        self.assertEqual(tsh["reference_high"], 4.0)
        self.assertEqual(tsh["status"], "Not above the reported upper limit")

        hdl = _by_name(results, "hdl")
        self.assertIsNone(hdl["reference_high"])
        self.assertEqual(hdl["reference_low"], 40)
        self.assertEqual(hdl["status"], "Not below the reported lower limit")

        sodium = _by_name(results, "sodium")
        self.assertEqual(sodium["value"], 139)
        self.assertIsNone(sodium["reference_low"])
        self.assertEqual(sodium["reference_high"], 145)
        self.assertEqual(sodium["status"], "Not above the reported upper limit")

    def test_equal_bounds_are_within_range(self):
        results = extract_lab_results("Hemoglobin 12.0 g/dL 12.0 - 16.0")
        self.assertEqual(results[0]["status"], "Within the reported range")

    def test_dates_and_non_results_are_ignored(self):
        results = extract_lab_results("\n".join([
            "Date of birth 01-15-1990",
            "Phone 555 123-4567",
            "Page 1 of 2",
            "See comment",
        ]))
        self.assertEqual(results, [])

    def test_non_text_input_returns_no_rows(self):
        self.assertEqual(extract_lab_results(None), [])
        self.assertEqual(extract_lab_results(12), [])


class RetrievalTests(unittest.TestCase):
    def test_aliases_find_glossary_entries(self):
        haemoglobin = retrieve_information("What does my hemoglobin mean?")
        self.assertTrue(any(item["title"] == "Haemoglobin" for item in haemoglobin))

        white_cells = retrieve_information("Explain the WBC count")
        self.assertTrue(any(item["title"] == "White blood cells" for item in white_cells))

        cbc = retrieve_information("What is the purpose of a CBC test?")
        self.assertTrue(any(item["title"] == "Complete blood count" for item in cbc))

    def test_blank_question_retrieves_nothing(self):
        self.assertEqual(retrieve_information("  "), [])


class ConsentAndChatTests(unittest.TestCase):
    def test_report_is_withheld_without_consent(self):
        report = "Hemoglobin 13.5 g/dL 12.0 - 16.0"
        labs = extract_lab_results(report)
        history = [
            {"role": "user", "content": "My hemoglobin was 13.5", "used_report": True},
            {"role": "assistant", "content": "The report shows 13.5.", "used_report": True},
            {"role": "user", "content": "What is glucose?", "used_report": False},
        ]

        withheld, withheld_labs, withheld_history = prepare_model_context(
            report,
            False,
            labs,
            history,
        )
        self.assertEqual(withheld, "")
        self.assertEqual(withheld_labs, [])
        self.assertEqual(
            [item["content"] for item in withheld_history],
            ["What is glucose?"],
        )

        shared, shared_labs, shared_history = prepare_model_context(
            report,
            True,
            labs,
            history,
        )
        self.assertIn("Hemoglobin", shared)
        self.assertEqual(shared_labs[0]["test_name"], "Hemoglobin")
        self.assertEqual(len(shared_history), 3)
        self.assertEqual(report_context_for_model(report, False), "")

    def test_missing_api_key_does_not_call_the_model(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            with patch("backend.chatbot.genai.Client") as client:
                result = answer_question("What is haemoglobin?")
        client.assert_not_called()
        self.assertIn("GEMINI_API_KEY", result["answer"])
        self.assertEqual(result["sources"], [])

    def test_prompt_contains_report_only_when_it_is_supplied(self):
        captured = {}

        class FakeModels:
            def generate_content(self, model, contents):
                captured["model"] = model
                captured["prompt"] = contents
                response = type("Response", (), {"text": "Educational answer."})()
                return response

        class FakeClient:
            def __init__(self, api_key):
                captured["api_key_was_passed"] = bool(api_key)
                self.models = FakeModels()

        with patch.dict(os.environ, {
            "GEMINI_API_KEY": "unit-test-not-a-real-key",
            "GEMINI_MODEL": "test-model",
        }):
            with patch("backend.chatbot.genai.Client", FakeClient):
                answer_question("What is glucose?", report_text="")
                self.assertIn("No medical report has been provided.", captured["prompt"])
                self.assertNotIn("Hemoglobin 13.5", captured["prompt"])

                answer_question(
                    "Explain my report",
                    report_text="Hemoglobin 13.5 g/dL 12.0 - 16.0",
                    lab_results=[{
                        "test_name": "Hemoglobin",
                        "value_text": "13.5",
                        "unit": "g/dL",
                        "reference_text": "12.0 - 16.0",
                        "status": "Within the reported range",
                    }],
                    history=[{
                        "role": "user",
                        "content": "Earlier general question",
                        "used_report": False,
                    }],
                )

        self.assertIn("Hemoglobin 13.5 g/dL 12.0 - 16.0", captured["prompt"])
        self.assertIn("Within the reported range", captured["prompt"])
        self.assertIn("Earlier general question", captured["prompt"])
        self.assertNotIn("unit-test-not-a-real-key", captured["prompt"])
        self.assertTrue(captured["api_key_was_passed"])
        self.assertEqual(captured["model"], "test-model")

    def test_parsed_rows_are_dropped_when_report_text_is_blank(self):
        captured = {}

        class FakeClient:
            def __init__(self, api_key):
                self.models = self

            def generate_content(self, model, contents):
                captured["prompt"] = contents
                return type("Response", (), {"text": "General educational answer."})()

        with patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-not-a-real-key"}):
            with patch("backend.chatbot.genai.Client", FakeClient):
                answer_question(
                    "What is a platelet?",
                    report_text="",
                    lab_results=[{
                        "test_name": "HiddenResult",
                        "value_text": "9",
                        "reference_text": "1 - 2",
                        "status": "Above the reported range",
                    }],
                    history=[
                        {
                            "role": "assistant",
                            "content": "The report value was 13.5.",
                            "used_report": True,
                        },
                    ],
                )
        self.assertNotIn("HiddenResult", captured["prompt"])
        self.assertNotIn("The report value was 13.5.", captured["prompt"])

    def test_api_failure_hides_the_key(self):
        class FakeClient:
            def __init__(self, api_key):
                self.models = self

            def generate_content(self, model, contents):
                raise RuntimeError("request failed for unit-test-not-a-real-key")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "unit-test-not-a-real-key"}):
            with patch("backend.chatbot.genai.Client", FakeClient):
                with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                    result = answer_question("What is glucose?")
                printed = stdout.getvalue()
        self.assertNotIn("unit-test-not-a-real-key", result["answer"])
        self.assertNotIn("unit-test-not-a-real-key", printed)
        self.assertIn("couldn't generate a response", result["answer"])
        self.assertEqual(result["sources"], [])

    def test_blank_question_is_rejected_before_the_api(self):
        with patch("backend.chatbot.genai.Client") as client:
            result = answer_question("   ")
        client.assert_not_called()
        self.assertIn("Please enter a question", result["answer"])


class UploadTests(unittest.TestCase):
    def test_text_pdf_png_and_jpg(self):
        pdf_bytes = _text_pdf((
            "Hemoglobin 13.5 g/dL 12.0 - 16.0",
            "Glucose 110 mg/dL 70 - 99",
        ))
        pdf_text = extract_report_text(pdf_bytes, "report.pdf")
        self.assertIn("Hemoglobin", pdf_text)
        pdf_results = extract_lab_results(pdf_text)
        self.assertEqual(_by_name(pdf_results, "hemoglobin")["status"], "Within the reported range")
        self.assertEqual(_by_name(pdf_results, "glucose")["status"], "Above the reported range")

        image = _report_image((
            "Hemoglobin 13.5 g/dL 12.0 - 16.0",
            "Glucose 110 mg/dL 70 - 99",
        ))
        png_bytes = _image_bytes(image, "PNG")
        jpg_bytes = _image_bytes(image, "JPEG")
        self.assertTrue(png_bytes.startswith(b"\x89PNG"))
        self.assertTrue(jpg_bytes.startswith(b"\xff\xd8\xff"))

        for filename, payload in (("report.png", png_bytes), ("report.jpg", jpg_bytes)):
            text = extract_report_text(payload, filename)
            results = extract_lab_results(text)
            hemoglobin = _by_name(results, "hemo")
            self.assertEqual(hemoglobin["value"], 13.5)
            self.assertEqual(hemoglobin["status"], "Within the reported range")
            glucose = _by_name(results, "glucose")
            self.assertEqual(glucose["status"], "Above the reported range")

    def test_scanned_pdf_uses_ocr(self):
        image = _report_image(("Potassium 4.2 mmol/L 3.5 - 5.1",))
        png_bytes = _image_bytes(image, "PNG")
        document = fitz.open()
        page = document.new_page(width=image.width, height=image.height)
        page.insert_image(page.rect, stream=png_bytes)
        self.assertFalse(page.get_text().strip())
        scanned = document.tobytes()
        document.close()

        text = extract_report_text(scanned, "scan.pdf")
        potassium = _by_name(extract_lab_results(text), "potassium")
        self.assertEqual(potassium["value"], 4.2)
        self.assertEqual(potassium["status"], "Within the reported range")

    def test_unreadable_files_raise_clear_errors(self):
        with self.assertRaises(ReportReadError):
            extract_report_text(b"", "empty.pdf")
        with self.assertRaises(ReportReadError):
            extract_report_text(b"not a report", "notes.txt")
        with self.assertRaises(ReportReadError):
            extract_report_text(b"%PDF-1.7\nthis is not a pdf", "broken.pdf")


class AppFlowTests(unittest.TestCase):
    def test_startup_upload_consent_and_general_question(self):
        from streamlit.testing.v1 import AppTest

        captured = []

        def fake_answer(question, report_text="", lab_results=None, history=None):
            captured.append({
                "question": question,
                "report_text": report_text,
                "lab_results": lab_results,
                "history": history,
            })
            return {
                "answer": "Educational test answer, not a diagnosis.",
                "sources": [{
                    "title": "Blood glucose",
                    "text": "Glucose is measured in blood.",
                    "source": "MedExplain educational glossary",
                }],
            }

        pdf_bytes = _text_pdf(("Hemoglobin 13.5 g/dL 12.0 - 16.0",))

        with patch("backend.chatbot.answer_question", side_effect=fake_answer):
            app = AppTest.from_file(
                str(ROOT / "frontend" / "app.py"),
                default_timeout=30,
            )
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertIn("MedExplain AI", app.title[0].value)

            app.sidebar.radio[0].set_value("Ask a Question").run()
            app.chat_input[0].set_value("What is a CBC test?").run()
            self.assertEqual(captured[-1]["report_text"], "")
            self.assertEqual(captured[-1]["lab_results"], [])
            self.assertEqual(captured[-1]["question"], "What is a CBC test?")

            app.sidebar.radio[0].set_value("My Medical Report").run()
            app.file_uploader[0].set_value(
                ("report.pdf", pdf_bytes, "application/pdf")
            ).run()
            extract = next(
                button for button in app.button
                if button.label == "Extract and Analyze Report"
            )
            extract.click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertIn("Hemoglobin", app.text_area[0].value)
            page_text = " ".join(markdown.value for markdown in app.markdown)
            self.assertIn("Within the reported range", page_text)
            self.assertIn("not a diagnosis", page_text.casefold())

            app.sidebar.radio[0].set_value("Ask a Question").run()
            app.chat_input[0].set_value("Explain my hemoglobin").run()
            self.assertEqual(captured[-1]["report_text"], "")
            self.assertEqual(captured[-1]["lab_results"], [])

            app.sidebar.radio[0].set_value("My Medical Report").run()
            app.checkbox[0].set_value(True).run()
            app.sidebar.radio[0].set_value("Ask a Question").run()
            app.chat_input[0].set_value("Explain my hemoglobin").run()

        consented = captured[-1]
        self.assertIn("Hemoglobin 13.5", consented["report_text"])
        self.assertEqual(consented["lab_results"][0]["status"], "Within the reported range")
        self.assertTrue(
            any(item["content"] == "Explain my hemoglobin" for item in consented["history"])
        )
        self.assertEqual(len(app.exception), 0)


def _text_pdf(lines):
    document = fitz.open()
    page = document.new_page()
    y_position = 72
    for line in lines:
        page.insert_text((72, y_position), line, fontsize=14)
        y_position += 28
    payload = document.tobytes()
    document.close()
    return payload


def _report_image(lines):
    font = ImageFont.truetype(FONT_PATH, 42)
    image = Image.new("RGB", (1600, 140 + 90 * len(lines)), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((50, 40 + index * 90), line, fill="black", font=font)
    return image


def _image_bytes(image, image_format):
    buffer = io.BytesIO()
    image.save(buffer, format=image_format, quality=95)
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
