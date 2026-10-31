
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
from backend.chatbot import answer_question


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
    st.checkbox(
        "I understand that report text may be sent to the configured "
        "AI service if I choose to ask a question about it.",
        key="ai_consent",
        value=False,
    )

    if uploaded_file is not None:

        st.caption(f"Selected file: {uploaded_file.name}")

        if st.button("Extract and Analyze Report", type="primary"):

            file_bytes = uploaded_file.getvalue()
            file_extension = Path(uploaded_file.name).suffix.lower()

            try:
                with st.spinner("Reading your report..."):

                    # DEBUG INFORMATION
                    st.write("Uploaded filename:", uploaded_file.name)
                    st.write("Detected extension:", file_extension)

                    # Pass the real filename to the OCR function.
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

            except Exception as error:
                st.error("Report processing failed.")
                st.exception(error)

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
                st.dataframe(results, use_container_width=True)
            else:
                st.info(
                    "No laboratory rows were recognized. You can still "
                    "review the extracted report text above."
                )

        elif isinstance(results, (list, tuple)):
            if results:
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

        st.session_state.chat_history.append(
            {"role": "user", "content": question}
        )

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):

            with st.spinner("MedExplain AI is thinking..."):

                try:

                    report_context = ""

                    # Include report only when user has consented
                    if (
                        st.session_state.report_text
                        and st.session_state.get("ai_consent", False)
                    ):
                        report_context = (
                            st.session_state.report_text[:12000]
                        )

                    response = answer_question(
                        question,
                        report_text=report_context
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
                                st.write(source)

                    st.session_state.chat_history.append(
                        {
                            "role": "assistant",
                            "content": str(answer)
                        }
                    )

                except Exception as error:

                    st.error(
                        "Sorry, I couldn't generate an answer. "
                        "Please try again."
                    )

                    st.exception(error)


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
        - Basic laboratory result parsing
        - Educational question answering
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
