# Workflow

## Read a report

```mermaid
flowchart TD
    start[Open My Medical Report]
    choose[Choose a PDF PNG or JPG]
    extract[Select Extract and Analyze Report]
    text[Store extracted text in the session]
    rows[Store parsed laboratory rows]
    review[Review counts cards and source text]
    clear[Clear Current Report]

    start --> choose --> extract --> text --> rows --> review
    review --> clear
    clear --> start
```

1. The file type is decided from the file bytes. The filename is only a fallback.
2. A PDF with a text layer returns that text. A PDF with no text, or a PNG or JPG, is sent to Tesseract.
3. Each kept row has a test name and a numeric value. A reference range is copied from the same line, or from the following line when that line is only a range.
4. If a bound is missing, it stays empty. The status text says that the result was not placed in a full range.
5. Every extracted row is marked for manual review.

Clearing the report removes the text, the rows, the filename, and the chat from the session. Closing the browser tab ends the session as well. The app does not save the upload to a project folder.

## Ask a question

```mermaid
flowchart TD
    ask[Open Ask a Question]
    hasReport{Report loaded?}
    consent{Consent on?}
    withReport[Include report text and parsed rows]
    withoutReport[Omit report text and parsed rows]
    history[Add recent chat turns]
    model[Call Gemini or report a missing key]
    show[Append the reply to the visible chat]

    ask --> hasReport
    hasReport -->|no| withoutReport
    hasReport -->|yes| consent
    consent -->|yes| withReport
    consent -->|no| withoutReport
    withReport --> history
    withoutReport --> history
    history --> model --> show
```

Consent is stored separately from the checkbox widget so it still applies after the user leaves **My Medical Report**. Turning the checkbox off stops later questions from including the report. Older replies that were created with the report are hidden from the model while consent is off. They can still be visible in the chat until **Clear Chat** is used.

Suggested questions use the same path as a typed question. They do not bypass consent.

## Status words

| Stored status | Dashboard group |
| --- | --- |
| Within the reported range | Within range |
| Below the reported range, or below a printed lower limit | Below range |
| Above the reported range, or above a printed upper limit | Above range |
| No range, or a one-sided limit that was not crossed | Not classified |

Not classified is not the same as a normal result. The chart caption says that no extra range was added.
