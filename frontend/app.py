import html
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# --------------------------------------------------
# PROJECT PATH
# --------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --------------------------------------------------
# BACKEND IMPORTS
# --------------------------------------------------
from backend.ocr import extract_report_text, verify_tesseract
from backend.report_analyzer import extract_lab_results, summarize_lab_results
from backend.chatbot import answer_question, prepare_model_context


SUGGESTED_QUESTIONS = [
    "Explain my report in simple words.",
    "What does haemoglobin mean?",
    "Which results are outside their reference ranges?",
    "What does glucose measure?",
    "Explain my creatinine result.",
]


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------
st.set_page_config(
    page_title="MedExplain AI",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------
# CUSTOM CSS
# --------------------------------------------------
st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: "Segoe UI", "Source Sans 3", sans-serif;
    }

    .stApp {
        background: #f4f7f4;
        color: #24312a;
    }

    [data-testid="stSidebar"] {
        background: #eef5f0;
        border-right: 1px solid #d7e6db;
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 1.4rem;
    }

    .block-container {
        padding-top: 1.6rem;
        padding-bottom: 3rem;
        max-width: 1120px;
    }

    .hero {
        background: linear-gradient(135deg, #ffffff 0%, #f3f7f3 55%, #f4f1fb 100%);
        border: 1px solid #dce8df;
        border-radius: 22px;
        padding: 32px 34px 26px;
        margin-bottom: 22px;
    }

    .brand-kicker {
        color: #6d7f86;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .main-title {
        font-size: 44px;
        line-height: 1.1;
        font-weight: 700;
        color: #345744;
        margin: 0 0 8px;
    }

    .subtitle {
        color: #5c6d63;
        font-size: 18px;
        line-height: 1.5;
        margin: 0;
    }

    .section-title {
        color: #345744;
        font-size: 22px;
        font-weight: 700;
        margin: 8px 0 12px;
    }

    .info-card, .lavender-card, .step-card, .disclaimer, .result-card {
        border-radius: 16px;
        padding: 18px 18px 14px;
        margin-bottom: 12px;
    }

    .info-card, .step-card {
        background: #ffffff;
        border: 1px solid #e1ece4;
    }

    .lavender-card {
        background: #f6f3fb;
        border: 1px solid #e4def3;
    }

    .step-number {
        display: inline-block;
        background: #e7f3ea;
        color: #345744;
        border-radius: 999px;
        padding: 2px 10px;
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .disclaimer {
        background: #f7f6f2;
        border: 1px solid #e6e1d6;
        color: #4e584f;
        font-size: 14px;
        line-height: 1.5;
    }

    .status-pill {
        display: inline-block;
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .status-within { background: #e5f4ea; color: #24613c; }
    .status-below { background: #f8f1e3; color: #7a5524; }
    .status-above { background: #f8ecec; color: #8a4545; }
    .status-other { background: #f3f0fa; color: #5d5478; }

    .review-note {
        color: #6a6258;
        font-size: 13px;
        margin-top: 6px;
    }

    div.stButton > button {
        background: #6f9780;
        color: #ffffff;
        border-radius: 12px;
        border: 1px solid #6f9780;
        padding: 0.45rem 0.9rem;
        font-weight: 600;
        transition: background 0.15s ease, border-color 0.15s ease;
    }

    div.stButton > button:hover {
        background: #5d846e;
        border-color: #5d846e;
        color: #ffffff;
    }

    div.stButton > button[kind="secondary"],
    div[data-testid="stDownloadButton"] > button {
        background: #ffffff;
        color: #345744;
        border: 1px solid #c9ddd0;
    }

    div[data-testid="stDownloadButton"] > button:hover {
        background: #f3f8f4;
        color: #345744;
        border-color: #6f9780;
    }

    [data-testid="stChatMessage"] {
        background: #ffffff;
        border: 1px solid #e3eee6;
        border-radius: 16px;
        padding: 6px 8px;
        margin-bottom: 8px;
    }

    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e1ece4;
        border-radius: 16px;
        padding: 10px 14px;
    }

    [data-testid="stFileUploader"] {
        background: #ffffff;
        border-radius: 16px;
        padding: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------
if "report_text" not in st.session_state:
    st.session_state.report_text = ""

if "report_results" not in st.session_state:
    st.session_state.report_results = None

if "report_filename" not in st.session_state:
    st.session_state.report_filename = ""

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "ai_consent" not in st.session_state:
    st.session_state.ai_consent = False

if "ocr_status" not in st.session_state:
    st.session_state.ocr_status = "Not started"

if "ocr_detail" not in st.session_state:
    st.session_state.ocr_detail = "No file has been read in this session."

if "go_to_report" not in st.session_state:
    st.session_state.go_to_report = False

if "tesseract_status" not in st.session_state:
    # One lightweight check at session start. No report text is involved.
    st.session_state.tesseract_status = verify_tesseract()


def _status_class(status):
    if status == "Within the reported range":
        return "status-within"
    if isinstance(status, str) and status.startswith("Below"):
        return "status-below"
    if isinstance(status, str) and status.startswith("Above"):
        return "status-above"
    return "status-other"


def _show_lab_results(results):
    """Show one card for each extracted row, using only parsed fields."""
    summary = summarize_lab_results(results)
    _show_summary(summary)

    if summary["total"] == 0:
        st.info(
            "No laboratory rows were recognized. Check the extracted "
            "text below. Missing values were not filled in."
        )
        return

    st.markdown('<p class="section-title">Result status</p>', unsafe_allow_html=True)
    chart = pd.DataFrame(
        {
            "Status": [
                "Within range",
                "Below range",
                "Above range",
                "Not classified",
            ],
            "Count": [
                summary["within"],
                summary["below"],
                summary["above"],
                summary["not_classified"],
            ],
        }
    )
    st.bar_chart(
        chart,
        x="Status",
        y="Count",
        color="#7d9e8a",
        sort=False,
        height=260,
    )
    st.caption(
        "Not classified means the line had no full range, or only a "
        "one-sided limit that was not crossed. No extra range was added."
    )

    st.markdown('<p class="section-title">Laboratory results</p>', unsafe_allow_html=True)
    for item in results:
        _show_result_card(item)


def _show_summary(summary):
    total, within, below, above = st.columns(4)
    total.metric("Detected tests", summary["total"])
    within.metric("Within range", summary["within"])
    below.metric("Below range", summary["below"])
    above.metric("Above range", summary["above"])
    if summary["not_classified"]:
        st.caption(
            f"{summary['not_classified']} result"
            f"{'' if summary['not_classified'] == 1 else 's'} "
            "could not be placed below, within, or above a full reported range."
        )


def _show_result_card(item):
    name = item.get("test_name") or "Result"
    value = item.get("value_text", item.get("value", ""))
    unit = item.get("unit") or "Unit not printed"
    reference = item.get("reference_text") or "Not printed on the extracted line"
    status = item.get("status") or "Not compared"
    explanation = item.get("explanation") or ""
    with st.container(border=True):
        st.markdown(
            f'<span class="status-pill {_status_class(status)}">{status}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**{name}**")
        left, right = st.columns(2)
        left.write(f"Measured value: {value}")
        left.write(f"Unit: {unit}")
        right.write(f"Printed reference: {reference}")
        if explanation:
            st.write(explanation)
        if item.get("needs_review", True):
            st.markdown(
                '<p class="review-note">Manual review: compare this row '
                "with the original report before relying on it.</p>",
                unsafe_allow_html=True,
            )


def _show_source(source):
    if isinstance(source, dict):
        title = source.get("title") or "Educational information"
        st.markdown(f"**{title}**")
        text = source.get("text") or ""
        if text:
            st.write(text)
        label = source.get("source") or ""
        if label:
            st.caption(str(label))
        return
    st.write(source)


def _ask(question):
    """Send one question, including report context only when consent allows it."""
    consent = bool(st.session_state.get("ai_consent", False))
    report_context, lab_context, prior_history = prepare_model_context(
        st.session_state.report_text,
        consent,
        st.session_state.report_results,
        st.session_state.chat_history,
    )
    used_report = bool(report_context)

    st.session_state.chat_history.append(
        {
            "role": "user",
            "content": question,
            "used_report": used_report,
        }
    )

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("MedExplain AI is thinking..."):
            try:
                response = answer_question(
                    question,
                    report_text=report_context,
                    lab_results=lab_context,
                    history=prior_history,
                )
                if isinstance(response, dict):
                    answer = response.get(
                        "answer",
                        "Sorry, no answer was returned.",
                    )
                    sources = response.get("sources", [])
                else:
                    answer = str(response)
                    sources = []

                st.markdown(answer)
                if sources:
                    with st.expander("Educational sources"):
                        for source in sources:
                            _show_source(source)

                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": str(answer),
                        "used_report": used_report,
                    }
                )
            except Exception:
                fallback = (
                    "Sorry, I couldn't generate an answer. "
                    "Please try again."
                )
                st.error(fallback)
                st.session_state.chat_history.append(
                    {
                        "role": "assistant",
                        "content": fallback,
                        "used_report": used_report,
                    }
                )


# --------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------
st.sidebar.markdown(
    '<p class="brand-kicker">Educational health tool</p>',
    unsafe_allow_html=True,
)
st.sidebar.title("MedExplain AI")
st.sidebar.caption("Plain-language help for medical reports")

if st.session_state.go_to_report:
    st.session_state.navigation = "My Medical Report"
    st.session_state.go_to_report = False

page = st.sidebar.radio(
    "Navigation",
    [
        "Home",
        "My Medical Report",
        "Ask a Question",
        "About",
    ],
    key="navigation",
)

st.sidebar.markdown("---")
if st.session_state.report_filename:
    st.sidebar.caption(f"Current file: {st.session_state.report_filename}")
else:
    st.sidebar.caption("No report uploaded")

if st.session_state.ai_consent:
    st.sidebar.caption("AI consent: on")
else:
    st.sidebar.caption("AI consent: off")

tesseract_status = st.session_state.tesseract_status
if tesseract_status.get("available"):
    version = tesseract_status.get("version") or "installed"
    st.sidebar.caption(f"OCR: Tesseract {version}")
else:
    st.sidebar.caption("OCR: Tesseract unavailable")
    st.sidebar.caption(
        "Text PDFs still work. Scanned PDFs and images need Tesseract."
    )

st.sidebar.caption("Educational support only — not a medical diagnosis.")


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------
if page == "Home":

    st.markdown(
        """
        <section class="hero">
            <p class="brand-kicker">MedExplain AI</p>
            <p class="main-title">Understand a report in plain language.</p>
            <p class="subtitle">
                Upload a laboratory report, review the values that can be
                read from it, and ask educational questions. MedExplain AI
                explains wording. It does not diagnose or recommend treatment.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Upload a medical report", type="primary"):
        st.session_state.go_to_report = True
        st.rerun()

    st.markdown('<p class="section-title">How it works</p>', unsafe_allow_html=True)
    step_one, step_two, step_three = st.columns(3)
    with step_one:
        st.markdown(
            """
            <div class="step-card">
                <div class="step-number">Step 1</div>
                <h4>Upload</h4>
                <p>Add a PDF, PNG, or JPG. Text is read from the file, and a scan uses OCR.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with step_two:
        st.markdown(
            """
            <div class="step-card">
                <div class="step-number">Step 2</div>
                <h4>Review</h4>
                <p>See detected tests, the printed range, and whether the value sits below, inside, or above it.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with step_three:
        st.markdown(
            """
            <div class="lavender-card">
                <div class="step-number">Step 3</div>
                <h4>Ask</h4>
                <p>Ask a general question, or allow the report to be sent to the AI service with consent.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<p class="section-title">What you can do</p>', unsafe_allow_html=True)
    feature_one, feature_two = st.columns(2)
    with feature_one:
        st.markdown(
            """
            <div class="info-card">
                <h4>Report reading</h4>
                <p>PDF text and image OCR for PNG and JPG reports.</p>
            </div>
            <div class="info-card">
                <h4>Range comparison</h4>
                <p>Values are compared only with a range printed on the extracted line.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with feature_two:
        st.markdown(
            """
            <div class="lavender-card">
                <h4>Simple explanations</h4>
                <p>Each detected test gets a short educational note, with a reminder to check the original.</p>
            </div>
            <div class="info-card">
                <h4>Questions</h4>
                <p>Ask about terms with or without a report. Report text is sent only after consent.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="disclaimer">
            <strong>Medical safety.</strong>
            MedExplain AI is not a doctor. It cannot diagnose a condition,
            prescribe medicine, or replace care from a qualified professional.
            OCR and parsing can miss or misread a number. Confirm every value
            and reference range against the original report.
        </div>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------
# MEDICAL REPORT PAGE
# --------------------------------------------------
elif page == "My Medical Report":

    st.title("My Medical Report")
    st.write(
        "Upload a de-identified report. The dashboard shows only values "
        "and ranges that were read from the file."
    )

    upload_column, status_column = st.columns([1.3, 1])
    with upload_column:
        uploaded_file = st.file_uploader(
            "Choose your medical report",
            type=["pdf", "png", "jpg", "jpeg"],
            help="Supported formats: PDF, PNG, JPG, and JPEG.",
        )
    with status_column:
        if st.session_state.report_filename:
            shown_name = st.session_state.report_filename
        elif uploaded_file is not None:
            shown_name = uploaded_file.name
        else:
            shown_name = "none selected"
        st.markdown(
            f"""
            <div class="info-card">
                <p><strong>File:</strong> {html.escape(shown_name)}</p>
                <p><strong>Reading status:</strong> {html.escape(st.session_state.ocr_status)}</p>
                <p>{html.escape(st.session_state.ocr_detail)}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.warning(
        "Use a fictional or de-identified report when possible. "
        "The file stays in this browser session and is not saved by the app."
    )

    # The checkbox key disappears when this page is not shown. Mirror it
    # into ai_consent so the choice still applies on Ask a Question, and
    # restore the checkbox when the user comes back.
    if "ai_consent_box" not in st.session_state:
        st.session_state.ai_consent_box = st.session_state.ai_consent
    consent_checked = st.checkbox(
        "I understand that report text may be sent to the configured "
        "AI service if I choose to ask a question about it.",
        key="ai_consent_box",
    )
    st.session_state.ai_consent = bool(consent_checked)
    if st.session_state.ai_consent:
        st.caption("AI consent is on. A later question may include this report.")
    else:
        st.caption("AI consent is off. Questions will not include this report.")

    if uploaded_file is not None:
        st.caption(f"Selected file: {uploaded_file.name}")
        if st.session_state.ocr_status == "Not started":
            st.session_state.ocr_detail = "A file is selected and has not been read yet."

        if st.button("Extract and Analyze Report", type="primary"):
            file_bytes = uploaded_file.getvalue()
            try:
                with st.spinner("Reading your report..."):
                    extracted_text = extract_report_text(
                        file_bytes,
                        uploaded_file.name,
                    )
                    if not isinstance(extracted_text, str):
                        raise TypeError(
                            "extract_report_text() did not return text. "
                            f"Received: {type(extracted_text).__name__}"
                        )
                    if not extracted_text.strip():
                        raise ValueError(
                            "No readable text was found. Try a clearer "
                            "image or a PDF with better-quality pages."
                        )
                    results = extract_lab_results(extracted_text)
                    st.session_state.report_text = extracted_text
                    st.session_state.report_results = results
                    st.session_state.report_filename = uploaded_file.name
                    st.session_state.chat_history = []
                    st.session_state.ocr_status = "Text extracted"
                    st.session_state.ocr_detail = (
                        f"Read {uploaded_file.name} in this session."
                    )
                st.rerun()
            except ValueError as error:
                st.session_state.ocr_status = "Reading failed"
                st.session_state.ocr_detail = str(error)
                st.rerun()
            except Exception:
                st.session_state.ocr_status = "Reading failed"
                st.session_state.ocr_detail = (
                    "The file could not be read. Use a PDF, PNG, or JPEG."
                )
                st.rerun()

        if st.session_state.ocr_status == "Text extracted":
            st.success("Report text extracted successfully!")
        elif st.session_state.ocr_status == "Reading failed":
            st.error(
                st.session_state.ocr_detail
                or "Report processing failed. Check that the file is a readable PDF, PNG, or JPEG."
            )

    if st.session_state.report_text:
        results = st.session_state.report_results
        st.markdown('<p class="section-title">Overview</p>', unsafe_allow_html=True)

        if results is None:
            _show_summary(summarize_lab_results([]))
            st.info(
                "The report text was extracted, but no analysis results "
                "are available."
            )
        elif isinstance(results, str):
            st.write(results)
        elif hasattr(results, "empty") and hasattr(results, "to_dict"):
            if not results.empty:
                st.dataframe(results, width="stretch")
            else:
                _show_summary(summarize_lab_results([]))
                st.info(
                    "No laboratory rows were recognized. You can still "
                    "review the extracted report text below."
                )
        elif isinstance(results, (list, tuple)):
            if results and all(isinstance(item, dict) for item in results):
                _show_lab_results(results)
            elif results:
                st.write(results)
            else:
                _show_summary(summarize_lab_results([]))
                st.info(
                    "No laboratory rows were recognized. Check the "
                    "extracted text below."
                )
        elif isinstance(results, dict):
            if results:
                st.json(results)
            else:
                st.info("No laboratory results were recognized.")
        else:
            st.write(results)

        st.markdown("---")
        st.subheader("Extracted report text")
        st.text_area(
            "Review the extracted text",
            value=st.session_state.report_text,
            height=220,
            disabled=True,
        )
        st.download_button(
            "Download Extracted Text",
            data=st.session_state.report_text,
            file_name="extracted_report.txt",
            mime="text/plain",
        )
        st.caption(
            "Extracted values and reference ranges may be inaccurate. "
            "Confirm them against the original report and consult a "
            "qualified healthcare professional."
        )
        if st.button("Clear Current Report"):
            st.session_state.report_text = ""
            st.session_state.report_results = None
            st.session_state.report_filename = ""
            st.session_state.chat_history = []
            st.session_state.ocr_status = "Not started"
            st.session_state.ocr_detail = "The previous report was cleared from this session."
            st.rerun()
    else:
        _show_summary(summarize_lab_results([]))
        st.info("Upload a PDF, PNG, or JPG report to see laboratory results.")


# --------------------------------------------------
# ASK A QUESTION PAGE
# --------------------------------------------------
elif page == "Ask a Question":

    st.title("Ask MedExplain AI")
    st.write(
        "Ask about a medical term, or about the uploaded report after "
        "you turn on AI consent."
    )

    if st.session_state.report_text:
        st.success(f"Report loaded: {st.session_state.report_filename}")
        if st.session_state.get("ai_consent", False):
            st.caption("Your report context is enabled for AI explanations.")
        else:
            st.warning(
                "Report context is not enabled. Visit My Medical Report "
                "and check the AI consent box to ask questions about "
                "your uploaded report."
            )
    else:
        st.info(
            "No report uploaded yet. You can still ask general "
            "educational questions."
        )

    st.markdown('<p class="section-title">Suggested questions</p>', unsafe_allow_html=True)
    suggestion_columns = st.columns(2)
    chosen_suggestion = None
    for index, suggestion in enumerate(SUGGESTED_QUESTIONS):
        if suggestion_columns[index % 2].button(suggestion, key=f"suggestion_{index}"):
            chosen_suggestion = suggestion

    header_left, header_right = st.columns([4, 1])
    with header_left:
        st.subheader("Your conversation")
    with header_right:
        if st.button("Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()

    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    typed_question = st.chat_input("Ask something in simple language...")
    question = typed_question or chosen_suggestion
    if question:
        _ask(question)

    st.caption(
        "Answers are educational and can be incomplete. "
        "This is not a medical diagnosis."
    )


# --------------------------------------------------
# ABOUT PAGE
# --------------------------------------------------
elif page == "About":

    st.title("About MedExplain AI")
    st.write(
        "An educational tool for reading the words and numbers on a "
        "laboratory report."
    )

    st.markdown('<p class="section-title">Overview</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="info-card">
        Medical reports are written for clinicians. MedExplain AI helps a
        reader see which laboratory rows can be extracted, how those values
        compare with the printed range, and what the test names mean in
        everyday language.
        </div>
        """,
        unsafe_allow_html=True,
    )

    problem, objectives = st.columns(2)
    with problem:
        st.markdown(
            """
            <div class="lavender-card">
            <h4>Problem</h4>
            <p>Report text is dense, scans are hard to search, and a number
            outside a printed range is easy to misunderstand.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with objectives:
        st.markdown(
            """
            <div class="info-card">
            <h4>Objectives</h4>
            <p>Read PDF and image reports, show only extracted values, explain
            test names, and answer questions without diagnosing.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<p class="section-title">Features</p>', unsafe_allow_html=True)
    st.markdown(
        """
        - PDF, PNG, and JPG text extraction
        - Laboratory rows with printed reference ranges
        - Below, within, and above comparisons when a full range is present
        - Short educational explanations
        - Questions with or without a report
        - Report context sent to the AI service only after consent
        - A local glossary for common test names
        - Download of the extracted text
        """
    )

    st.markdown('<p class="section-title">Technology</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="info-card">
        Python and Streamlit for the interface. PyMuPDF for PDF text.
        Tesseract OCR and Pillow for scans and images. A local TF-IDF
        glossary with scikit-learn. Google Gemini through google-genai,
        with the API key loaded from a <code>.env</code> file by python-dotenv.
        Pandas formats the status chart.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<p class="section-title">How a report moves through the app</p>', unsafe_allow_html=True)
    st.markdown(
        """
        1. The file stays in the browser session.
        2. Text is taken from the PDF, or from OCR for a scan or image.
        3. Lines that look like laboratory rows are parsed. Missing ranges stay empty.
        4. The dashboard counts and explains those rows.
        5. A question includes the report only when AI consent is on.
        """
    )

    st.markdown('<p class="section-title">Limitations</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="disclaimer">
        Parsing is line-based, so unusual tables can be missed. OCR depends
        on image quality and a local Tesseract install. Glossary notes are
        general and are not a personal interpretation. The app does not
        store an account, and it does not provide a diagnosis or a treatment plan.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<p class="section-title">Privacy and safety</p>', unsafe_allow_html=True)
    st.markdown(
        """
        - The Gemini API key is read from the environment, not from the page.
        - Report text is sent to Gemini only after the consent box is checked.
        - Uploaded files and chat text live in the session and are cleared when the report or chat is cleared, or when the session ends.
        - Error messages shown on the page do not include the API key.
        - Use a fictional or de-identified report whenever you can.
        - This is educational information, not a medical diagnosis.
        """
    )
    st.caption("MedExplain AI · Educational prototype")
