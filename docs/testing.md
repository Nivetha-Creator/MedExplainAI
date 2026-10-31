# Testing

Run the suite from the repository root:

```bash
python -m unittest discover -s tests -v
```

Tesseract must be installed for the image and scanned-PDF tests. A Gemini key is not required. The chatbot tests replace the Gemini client with a fake, or they remove the key from the environment for that test only.

## Phase 1 suite

`tests/test_phase1.py` checks:

- Full ranges, one-sided limits, wrapped rows, and lines that are dates or contact details
- Glossary aliases for haemoglobin, white blood cells, and a complete blood count
- Report text withheld when consent is off, including earlier report-based chat turns
- A missing API key, a prompt that contains a report only when one was supplied, and a failed call that does not reveal the test key
- Text PDF, PNG, JPG, and a scanned PDF
- Streamlit startup, upload, extraction, a general question, and consent through the page flow

## Phase 2 suite

`tests/test_phase2.py` checks:

- Status totals, including one-sided limits that must not be counted as within range
- Empty input counted as zero
- A failed Gemini call whose log and reply omit both the report text and the test key
- The five suggested questions
- Home, My Medical Report, Ask a Question, and About loading without an exception
- An empty dashboard with zero counts
- A two-row sample PDF whose dashboard counts are 2 detected, 1 within range, 1 above range, and 0 below range

## Latest local run

Command, run from the repository root on 31 October 2026 at 12:03 PM America/New_York:

```bash
python -m unittest discover -s tests -v
```

Result recorded with the final review: 24 tests ran, and all 24 passed. Seventeen are in `tests/test_phase1.py`. Seven are in `tests/test_phase2.py`. No live Gemini request was made.

Browser screenshots of a fictional report are in `docs/images/`. The unit tests do not create those images.

## Not covered

- A live Gemini response. No project API key is stored in the repository, and these tests do not call the network.
- Handwritten or low-quality scans beyond the generated images in the tests.
- Password-protected PDFs are rejected by the reader, but the suite uses a damaged PDF rather than an encrypted one.
- Browser screenshots are not produced by the unit tests.
