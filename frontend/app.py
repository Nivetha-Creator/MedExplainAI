
import sys
from pathlib import Path

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
from backend.ocr import extract_report_text
from backend.report_analyzer import extract_lab_results
from backend.chatbot import answer_question, prepare_model_context


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
    .stApp {
        background-color: #f7faf7;
    }

    [data-testid="stSidebar"] {
        background-color: #e9f3ed;
    }

    .main-title {
        font-size: 42px;
        font-weight: 800;
        color: #426b57;
        margin-bottom: 0;
    }

    .subtitle {
        color: #65766b;
        font-size: 17px;
        margin-top: 5px;
        margin-bottom: 25px;
    }

    .info-card {
        background-color: #edf5ef;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #d8e8dc;
        margin-bottom: 15px;
    }

    .lavender-card {
        background-color: #f0edfa;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #e1dbf4;
        margin-bottom: 15px;
    }

    .small-note {
        color: #68776d;
        font-size: 13px;
    }

    div.stButton > button {
        background-color: #769c82;
        color: white;
        border-radius: 10px;
        border: none;
        padding: 10px 20px;
        font-weight: 600;
    }

    div.stButton > button:hover {
        background-color: #5d8069;
        color: white;
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


def _show_lab_results(results):
    """Show parsed rows and the educational note for each one."""
    table = []
    for item in results:
        table.append({
            "Test": item.get("test_name", ""),
            "Result": item.get("value_text", item.get("value", "")),
            "Unit": item.get("unit", ""),
            "Reported reference range": item.get("reference_text", ""),
            "Comparison": item.get("status", ""),
        })

    st.dataframe(table, width="stretch", hide_index=True)

    st.markdown("#### Simple explanations")
    st.caption(
        "These notes use only the extracted row and a general glossary. "
        "They do not diagnose a condition or recommend treatment."
    )
    for item in results:
        name = item.get("test_name") or "Result"
        explanation = item.get("explanation") or item.get("status") or ""
        st.markdown(f"**{name}**")
        st.write(explanation)


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


# --------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------
st.sidebar.title("🩺 MedExplain AI")
st.sidebar.caption("Understand your health reports")

page = st.sidebar.radio(
    "Navigation",
    [
        "Home",
        "My Medical Report",
        "Ask a Question",
        "About",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption("Educational support only — not a medical diagnosis.")


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------
if page == "Home":

    st.markdown(
        '<p class="main-title">MedExplain AI 🩺</p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<p class="subtitle">'
        'Understand your medical reports in simple words.'
        '</p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="info-card">
            <h3>Welcome to MedExplain AI!</h3>
            <p>
            Medical reports can contain unfamiliar terms and laboratory
            measurements. This application helps explain report text
            in simpler language for educational purposes.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="info-card">
                <h3>📄 Report Reader</h3>
                <p>Upload a PDF or a PNG/JPEG image of a report.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            """
            <div class="lavender-card">
                <h3>🔍 Result Overview</h3>
                <p>Review text and possible laboratory values extracted
                from the uploaded report.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div class="info-card">
                <h3>💬 Ask Questions</h3>
                <p>Ask for educational explanations of medical terms.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### How to get started")

    st.write("1. Open **My Medical Report** from the sidebar.")
    st.write("2. Upload a PDF, PNG, or JPEG report.")
    st.write("3. Select **Extract and Analyze Report**.")
    st.write("4. Review the extracted text and results.")
    st.write("5. Open **Ask a Question** to ask about the report.")


# --------------------------------------------------
# MEDICAL REPORT PAGE
# --------------------------------------------------
elif page == "My Medical Report":

    st.title("📄 My Medical Report")

    st.write(
        "Upload a report to extract its text and review possible "
        "laboratory results."
    )

    uploaded_file = st.file_uploader(
        "Choose your medical report",
        type=["pdf", "png", "jpg", "jpeg"],
        help="Supported formats: PDF, PNG, JPG, and JPEG.",
    )

    st.warning(
        "Use a fictional or de-identified report when possible. "
        "Review extracted information carefully."
    )

    # The consent checkbox is required before sending report text
    # to the external AI service in the question page.
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

    if uploaded_file is not None:

        st.caption(f"Selected file: {uploaded_file.name}")

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

                    # Save the successful result.
                    st.session_state.report_text = extracted_text
                    st.session_state.report_results = results
                    st.session_state.report_filename = uploaded_file.name
                    st.session_state.chat_history = []

                st.success("Report text extracted successfully!")

            except ValueError as error:
                st.error(str(error))

            except Exception:
                st.error(
                    "Report processing failed. Check that the file is a "
                    "readable PDF, PNG, or JPEG, then try again."
                )

    # Display results retained in session state.
    if st.session_state.report_text:

        st.markdown("---")
        st.subheader("📝 Extracted Report Text")

        st.text_area(
            "Review the extracted text",
            value=st.session_state.report_text,
            height=250,
            disabled=True,
        )

        st.download_button(
            "Download Extracted Text",
            data=st.session_state.report_text,
            file_name="extracted_report.txt",
            mime="text/plain",
        )

        st.subheader("🔬 Possible Laboratory Results")

        results = st.session_state.report_results

        if results is None:
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
                st.info(
                    "No laboratory rows were recognized. You can still "
                    "review the extracted report text above."
                )

        elif isinstance(results, (list, tuple)):
            if results and all(isinstance(item, dict) for item in results):
                _show_lab_results(results)
            elif results:
                st.write(results)
            else:
                st.info(
                    "No laboratory rows were recognized. Check the "
                    "extracted text above."
                )

        elif isinstance(results, dict):
            if results:
                st.json(results)
            else:
                st.info("No laboratory results were recognized.")

        else:
            st.write(results)

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
            st.rerun()


# --------------------------------------------------
# ASK A QUESTION PAGE
# --------------------------------------------------
elif page == "Ask a Question":

    st.title("💬 Ask MedExplain AI")

    st.write(
        "Ask questions about your uploaded medical report "
        "or learn about medical terms in simple language."
    )

    # Show uploaded report information
    if st.session_state.report_text:

        st.success(
            f"Report loaded: {st.session_state.report_filename}"
        )

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

    st.markdown("---")

    # Clear conversation button
    col1, col2 = st.columns([4, 1])

    with col1:
        st.subheader("Your conversation")

    with col2:
        if st.button("Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()

    # Display previous messages
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Suggested questions
    with st.expander("💡 Try asking these questions"):
        st.write("- What does my hemoglobin level mean?")
        st.write("- Explain my glucose result.")
        st.write("- Which results are outside their reference ranges?")
        st.write("- What is the purpose of a CBC test?")
        st.write("- Explain my report in simple words.")
        st.write("- What questions should I ask my doctor?")

    # User question input
    question = st.chat_input(
        "Ask something about your medical report..."
    )

    if question:

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
                            "Sorry, no answer was returned."
                        )

                        sources = response.get("sources", [])

                    else:

                        answer = str(response)
                        sources = []

                    st.markdown(answer)

                    if sources:
                        with st.expander("📚 Educational Sources"):
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
# ABOUT PAGEs
# --------------------------------------------------
elif page == "About":

    st.title("🌿 About MedExplain AI")

    st.markdown(
        """
        MedExplain AI is an educational application designed to help
        users understand the wording in medical reports.

        **Features**
        - PDF and image text extraction
        - Laboratory result parsing with reported reference ranges
        - Simple educational explanations of extracted results
        - Educational question answering, with or without a report
        - Downloadable extracted text

        **Important limitations**

        This application is not a doctor and cannot diagnose diseases,
        prescribe medicines, or replace professional medical advice.
        Optical character recognition and automated parsing can make
        mistakes. Always compare extracted values and reference ranges
        with the original report and consult a qualified healthcare
        professional about medical concerns.
        """
    )

    st.markdown("---")
    st.caption("MedExplain AI · Educational prototype")
