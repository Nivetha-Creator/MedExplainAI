import re

from backend.rag import find_glossary_entry


NUMBER = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"

# Longer units must come first so "g/dL" is not read as "g".
UNIT = (
    r"(?:x\s*10\s*\^\s*9\s*/\s*L|x\s*10\s*\^\s*3\s*/\s*[uµ]L|"
    r"10\s*\^\s*9\s*/\s*L|10\s*\^\s*3\s*/\s*[uµ]L|"
    r"cells\s*/\s*[uµ]L|"
    r"mIU/L|µIU/mL|uIU/mL|IU/mL|IU/L|U/L|"
    r"mmol/mol|mmol/L|µmol/L|umol/L|"
    r"mg/dL|g/dL|ng/mL|ng/dL|pg/mL|µg/dL|ug/dL|"
    r"mEq/L|mg/L|g/L|mm/hr|mm/h|"
    r"/[uµ]L|fL|pg|%)"
)

PAIR_RANGE = re.compile(
    rf"[\(\[]?\s*(?P<low>{NUMBER})\s*-\s*(?P<high>{NUMBER})\s*[\)\]]?"
)
UPPER_RANGE = re.compile(
    rf"[\(\[]?\s*(?P<op><=|<)\s*(?P<high>{NUMBER})\s*[\)\]]?"
)
LOWER_RANGE = re.compile(
    rf"[\(\[]?\s*(?P<op>>=|>)\s*(?P<low>{NUMBER})\s*[\)\]]?"
)
VALUE_AT_END = re.compile(
    rf"^(?P<name>.*?)\s+(?P<value>{NUMBER})\s*(?P<unit>{UNIT})?\s*$",
    re.IGNORECASE,
)
RANGE_ONLY = re.compile(
    rf"^(?:(?:ref(?:erence)?|normal)\s*)?(?:range|interval)?\s*"
    rf"[\(\[]?\s*(?:{NUMBER}\s*-\s*{NUMBER}|(?:<=|<|>=|>)\s*{NUMBER})\s*[\)\]]?$",
    re.IGNORECASE,
)
LEADING_RANGE_LABEL = re.compile(
    r"(?:\b(?:ref|reference|normal|range|interval)\b[\s:]*)+$",
    re.IGNORECASE,
)
DATE_HINT = re.compile(
    r"\b(?:dob|date of birth|collected|collection date|printed|reported on|"
    r"specimen date|accession|phone|fax)\b",
    re.IGNORECASE,
)
BLOCKED_NAME = re.compile(
    r"^(?:date|time|page|phone|fax|dob|age|patient|name|doctor|physician|"
    r"address|comment|comments|note|notes|laboratory|lab|id|sample|"
    r"specimen|collected|printed|reported)$",
    re.IGNORECASE,
)

DISCLAIMER = (
    "This is educational information, not a diagnosis or a treatment "
    "recommendation."
)

WITHIN_RANGE = "Within the reported range"
BELOW_RANGE_STATUSES = {
    "Below the reported range",
    "Below the reported lower limit",
}
ABOVE_RANGE_STATUSES = {
    "Above the reported range",
    "Above the reported upper limit",
}


def extract_lab_results(report_text):
    """
    Extract possible laboratory rows from report text.

    A row is returned only when a test name and a numeric result are
    readable. Reference bounds are copied from the same line. Missing
    bounds stay empty, and a result is compared only with bounds that
    were actually read.
    """

    if not isinstance(report_text, str):
        return []

    results = []
    for line in _candidate_lines(report_text):
        parsed = _parse_line(line)
        if parsed is not None:
            results.append(parsed)
    return results


def _candidate_lines(report_text):
    raw_lines = []
    for line in report_text.splitlines():
        normalized = _normalize_line(line)
        if not normalized or len(normalized) > 300:
            continue
        if normalized.lower().startswith("--- page"):
            continue
        raw_lines.append(normalized)

    merged = []
    index = 0
    while index < len(raw_lines):
        current = raw_lines[index]
        if (
            index + 1 < len(raw_lines)
            and _has_value_and_unit(current)
            and not _has_range(current)
            and RANGE_ONLY.match(raw_lines[index + 1])
        ):
            merged.append(f"{current} {raw_lines[index + 1]}")
            index += 2
            continue
        merged.append(current)
        index += 1
    return merged


def _normalize_line(line):
    line = (
        line.replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
        .replace("≤", "<=")
        .replace("≥", ">=")
    )
    return re.sub(r"\s+", " ", line).strip()


def _has_range(line):
    return (
        PAIR_RANGE.search(line) is not None
        or UPPER_RANGE.search(line) is not None
        or LOWER_RANGE.search(line) is not None
    )


def _has_value_and_unit(line):
    match = VALUE_AT_END.match(line.strip())
    return bool(match and match.group("unit") and _clean_name(match.group("name")))


def _parse_line(line):
    if DATE_HINT.search(line) and re.search(r"\d{1,4}\s*-\s*\d{1,4}", line):
        return None

    for match in reversed(list(PAIR_RANGE.finditer(line))):
        parsed = _from_range(line, match, "pair")
        if parsed is not None:
            return parsed

    for pattern, kind in ((UPPER_RANGE, "upper"), (LOWER_RANGE, "lower")):
        for match in reversed(list(pattern.finditer(line))):
            parsed = _from_range(line, match, kind)
            if parsed is not None:
                return parsed

    return _from_value_only(line)


def _from_range(line, match, kind):
    prefix = line[:match.start()]
    prefix = LEADING_RANGE_LABEL.sub("", prefix).strip(" :-")
    value_match = VALUE_AT_END.match(prefix)
    if value_match is None:
        return None

    suffix = line[match.end():].strip(" :-")
    suffix_unit = re.match(rf"({UNIT})\b", suffix, flags=re.IGNORECASE)
    unit = value_match.group("unit") or ""
    if not unit and suffix_unit:
        unit = suffix_unit.group(1)

    try:
        value = float(value_match.group("value"))
    except ValueError:
        return None

    low = high = None
    low_text = high_text = ""
    low_inclusive = high_inclusive = False

    if kind == "pair":
        low_text = match.group("low")
        high_text = match.group("high")
        low = float(low_text)
        high = float(high_text)
        if low > high:
            return None
        low_inclusive = high_inclusive = True
        reference_text = f"{low_text} - {high_text}"
    elif kind == "upper":
        high_text = match.group("high")
        high = float(high_text)
        high_inclusive = match.group("op") == "<="
        reference_text = f"{match.group('op')} {high_text}"
    else:
        low_text = match.group("low")
        low = float(low_text)
        low_inclusive = match.group("op") == ">="
        reference_text = f"{match.group('op')} {low_text}"

    return _build_result(
        name=value_match.group("name"),
        value=value,
        value_text=value_match.group("value"),
        unit=_clean_unit(unit),
        low=low,
        high=high,
        low_inclusive=low_inclusive,
        high_inclusive=high_inclusive,
        reference_text=reference_text,
        source_line=line,
    )


def _from_value_only(line):
    match = VALUE_AT_END.match(line)
    if match is None or not match.group("unit"):
        return None
    try:
        value = float(match.group("value"))
    except ValueError:
        return None
    return _build_result(
        name=match.group("name"),
        value=value,
        value_text=match.group("value"),
        unit=_clean_unit(match.group("unit")),
        low=None,
        high=None,
        low_inclusive=False,
        high_inclusive=False,
        reference_text="",
        source_line=line,
    )


def _build_result(
    name,
    value,
    value_text,
    unit,
    low,
    high,
    low_inclusive,
    high_inclusive,
    reference_text,
    source_line,
):
    cleaned_name = _clean_name(name)
    if cleaned_name is None:
        return None
    if unit == "" and re.fullmatch(r"\d{4}", value_text):
        return None

    status = _status(value, low, high, low_inclusive, high_inclusive)
    explanation = _explanation(
        cleaned_name,
        value_text,
        unit,
        reference_text,
        status,
    )
    return {
        "test_name": cleaned_name,
        "value": value,
        "value_text": value_text,
        "unit": unit,
        "reference_low": low,
        "reference_high": high,
        "reference_text": reference_text,
        "status": status,
        "explanation": explanation,
        "source_line": source_line,
        "needs_review": True,
    }


def _clean_name(name):
    if not isinstance(name, str):
        return None
    cleaned = name.strip(" :-/|")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(
        r"^(?:test|result)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    words = cleaned.split()
    if len(words) > 8:
        cleaned = " ".join(words[-8:])
    if not cleaned or not re.search(r"[A-Za-z]", cleaned):
        return None
    if BLOCKED_NAME.match(cleaned):
        return None
    if len(cleaned) > 80:
        return None
    return cleaned


def _clean_unit(unit):
    if not unit:
        return ""
    return re.sub(r"\s+", "", unit)


def _status(value, low, high, low_inclusive, high_inclusive):
    if low is not None and high is not None:
        below = value < low if low_inclusive else value <= low
        above = value > high if high_inclusive else value >= high
        if below:
            return "Below the reported range"
        if above:
            return "Above the reported range"
        return "Within the reported range"

    if high is not None:
        above = value > high if high_inclusive else value >= high
        if above:
            return "Above the reported upper limit"
        return "Not above the reported upper limit"

    if low is not None:
        below = value < low if low_inclusive else value <= low
        if below:
            return "Below the reported lower limit"
        return "Not below the reported lower limit"

    return "No reference range was reported on this line"


def _explanation(name, value_text, unit, reference_text, status):
    entry = find_glossary_entry(name)
    if entry is not None:
        meaning = entry["text"]
    else:
        meaning = (
            f"{name} was read as a laboratory result on the uploaded report. "
            "No extra medical definition was added for this name."
        )

    measured = " ".join(part for part in (value_text, unit) if part)
    sentences = [
        meaning,
        f"The extracted result is {measured}.",
    ]
    if reference_text:
        sentences.append(
            f"The reference information read from that line is {reference_text}."
        )
        sentences.append(
            f"Comparison with only that reported information: {status}."
        )
    else:
        sentences.append(
            "No reference range was found on that line, so the result "
            "was not classified as below, within, or above a range."
        )
    sentences.append(DISCLAIMER)
    return " ".join(sentences)


def summarize_lab_results(results):
    """Count extracted rows by the comparison actually stored on each row."""
    if not isinstance(results, (list, tuple)):
        rows = []
    else:
        rows = [item for item in results if isinstance(item, dict)]

    within = below = above = not_classified = 0
    for item in rows:
        status = item.get("status") or ""
        if status == WITHIN_RANGE:
            within += 1
        elif status in BELOW_RANGE_STATUSES:
            below += 1
        elif status in ABOVE_RANGE_STATUSES:
            above += 1
        else:
            not_classified += 1

    return {
        "total": len(rows),
        "within": within,
        "below": below,
        "above": above,
        "not_classified": not_classified,
    }
