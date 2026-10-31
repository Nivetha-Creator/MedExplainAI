
import re

NUMBER = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"

UNIT = (
    r"(?:mg/dL|g/dL|mmol/L|umol/L|µmol/L|"
    r"mIU/L|uIU/mL|IU/L|U/L|ng/mL|pg/mL|"
    r"10\^?\d+/L|10\^?\d+|"
    r"cells/uL|cells/µL|/uL|/µL|"
    r"mg/L|g/L|mm/hr|fL|pg|%|mg|g)"
)


def extract_lab_results(report_text):
    """
    Extract possible laboratory results from OCR text.

    This prototype recognizes rows containing:
    Test name + result + optional unit + reference range.

    Every extracted result must be checked against the original report.
    """

    results = []

    if not isinstance(report_text, str):
        return results

    for line in report_text.splitlines():

        line = re.sub(r"\s+", " ", line).strip()

        if not line or len(line) > 250:
            continue

        if line.lower().startswith("--- page"):
            continue

        pattern = (
            rf"(?P<name>[A-Za-z][A-Za-z0-9 /()_'-]{{1,55}}?)"
            rf"\s+(?P<value>{NUMBER})"
            rf"(?:\s*(?P<unit>{UNIT}))?"
            rf"\s+(?P<range_low>{NUMBER})"
            rf"\s*[-–—]\s*"
            rf"(?P<range_high>{NUMBER})"
        )

        match = re.search(pattern, line, flags=re.IGNORECASE)

        if not match:
            continue

        try:
            name = match.group("name").strip(" :-")
            value = float(match.group("value"))
            low = float(match.group("range_low"))
            high = float(match.group("range_high"))

        except (ValueError, TypeError):
            continue

        if not name or low > high:
            continue

        if value < low:
            status = "Below the reported range"

        elif value > high:
            status = "Above the reported range"

        else:
            status = "Within the reported range"

        results.append({
            "test_name": name,
            "value": value,
            "unit": match.group("unit") or "",
            "reference_low": low,
            "reference_high": high,
            "status": status,
            "source_line": line,
            "needs_review": True,
        })

    return results
