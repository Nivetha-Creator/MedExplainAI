import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


MEDICAL_KNOWLEDGE = [
    {
        "title": "Laboratory reference ranges",
        "aliases": ["reference range", "reference interval", "normal range"],
        "text": (
            "A laboratory reference range describes values commonly "
            "seen in a specified reference population. Ranges can vary "
            "between laboratories, methods, and patient groups. A result "
            "outside a range does not by itself establish a diagnosis."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Haemoglobin",
        "aliases": ["haemoglobin", "hemoglobin", "hb", "hgb"],
        "text": (
            "Haemoglobin is a protein in red blood cells that carries "
            "oxygen. A haemoglobin result needs the laboratory's own "
            "range and the person's clinical context."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Haematocrit",
        "aliases": ["haematocrit", "hematocrit", "hct", "packed cell volume", "pcv"],
        "text": (
            "Haematocrit describes the proportion of blood made up of "
            "red blood cells. It is read together with the range printed "
            "by the laboratory."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Red blood cells",
        "aliases": ["red blood cells", "red blood cell", "rbc", "erythrocytes", "erythrocyte"],
        "text": (
            "Red blood cells carry oxygen through the blood. A red "
            "blood cell count by itself does not explain why the count "
            "changed."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "White blood cells",
        "aliases": ["white blood cells", "white blood cell", "wbc", "leukocytes", "leucocytes"],
        "text": (
            "White blood cells are part of the immune system. Their "
            "count can change for many reasons. A white blood cell "
            "result alone cannot identify the cause of a change."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Platelets",
        "aliases": ["platelets", "platelet", "platelet count", "plt"],
        "text": (
            "Platelets are blood components that help form clots. "
            "Platelet counts should be read with the reported reference "
            "interval and relevant clinical information."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Blood glucose",
        "aliases": ["glucose", "blood glucose", "blood sugar", "fasting glucose"],
        "text": (
            "Blood glucose measures the amount of glucose in the blood. "
            "Its meaning depends on the test type, timing, units, "
            "laboratory range, and clinical context."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "HbA1c",
        "aliases": ["hba1c", "a1c", "glycated haemoglobin", "glycated hemoglobin"],
        "text": (
            "HbA1c is a laboratory measure related to glucose attached "
            "to haemoglobin. It has to be read with the units and range "
            "printed on the report."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Creatinine",
        "aliases": ["creatinine"],
        "text": (
            "Creatinine is a waste product measured in blood or urine. "
            "Blood creatinine can be one piece of information about "
            "kidney function, but it does not by itself explain a "
            "person's health."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Urea",
        "aliases": ["urea", "blood urea"],
        "text": (
            "Urea is a waste product measured in blood. A urea result "
            "needs the laboratory range and other clinical information."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Sodium",
        "aliases": ["sodium"],
        "text": (
            "Sodium is a mineral measured in blood. The number on a "
            "report is interpreted with that laboratory's range."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Potassium",
        "aliases": ["potassium"],
        "text": (
            "Potassium is a mineral measured in blood. The result is "
            "interpreted with the range reported by the laboratory."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Total cholesterol",
        "aliases": ["cholesterol", "total cholesterol"],
        "text": (
            "Total cholesterol is a blood measurement of cholesterol. "
            "It is not a complete picture of cardiovascular health."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "HDL cholesterol",
        "aliases": ["hdl", "hdl cholesterol"],
        "text": (
            "HDL cholesterol is one type of cholesterol measured in "
            "blood. Compare it only with the range printed on the report."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "LDL cholesterol",
        "aliases": ["ldl", "ldl cholesterol"],
        "text": (
            "LDL cholesterol is one type of cholesterol measured in "
            "blood. Compare it only with the range printed on the report."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Triglycerides",
        "aliases": ["triglycerides", "triglyceride"],
        "text": (
            "Triglycerides are a type of fat measured in blood. The "
            "result depends on the laboratory range and the testing context."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "ALT",
        "aliases": ["alt", "alanine aminotransferase", "sgpt"],
        "text": (
            "ALT is an enzyme measured in blood and is often included "
            "in liver-related panels. An ALT number does not by itself "
            "identify a cause."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "AST",
        "aliases": ["ast", "aspartate aminotransferase", "sgot"],
        "text": (
            "AST is an enzyme measured in blood. It can appear in "
            "liver-related panels and needs the laboratory's range."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "TSH",
        "aliases": ["tsh", "thyroid stimulating hormone", "thyroid-stimulating hormone"],
        "text": (
            "TSH is a hormone signal related to the thyroid gland. "
            "A TSH result is interpreted with the range on the report "
            "and the person's clinical context."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Complete blood count",
        "aliases": ["complete blood count", "cbc", "full blood count", "fbc"],
        "text": (
            "A complete blood count is a panel of blood measurements, "
            "often including red cells, white cells, haemoglobin, and "
            "platelets. Each row still has to be read on its own."
        ),
        "source": "MedExplain educational glossary",
    },
]


def _entry_document(item):
    alias_text = " ".join(item.get("aliases", []))
    return f"{item['title']}. {alias_text}. {item['text']}"


_documents = [_entry_document(item) for item in MEDICAL_KNOWLEDGE]
_vectorizer = TfidfVectorizer(stop_words="english")
_matrix = _vectorizer.fit_transform(_documents)

_ALIAS_TO_ENTRY = {}
for _item in MEDICAL_KNOWLEDGE:
    for _alias in _item.get("aliases", []):
        _ALIAS_TO_ENTRY[_alias.casefold()] = _item
    _ALIAS_TO_ENTRY[_item["title"].casefold()] = _item


def _normalize_lookup(text):
    cleaned = text.casefold().replace("hemoglobin", "haemoglobin")
    cleaned = cleaned.replace("hematocrit", "haematocrit")
    cleaned = re.sub(r"[^a-z0-9+ ]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def find_glossary_entry(test_name):
    """Return the glossary entry whose alias matches a test name, if any."""
    if not isinstance(test_name, str) or not test_name.strip():
        return None

    normalized = _normalize_lookup(test_name)
    if normalized in _ALIAS_TO_ENTRY:
        return _ALIAS_TO_ENTRY[normalized]

    best_entry = None
    best_length = 0
    for alias, entry in _ALIAS_TO_ENTRY.items():
        if len(alias) < 2:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized):
            if len(alias) > best_length:
                best_entry = entry
                best_length = len(alias)
    return best_entry


def _expand_question(question):
    lowered = question.casefold()
    extras = []
    for alias, entry in _ALIAS_TO_ENTRY.items():
        if len(alias) < 2:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lowered):
            extras.append(entry["title"])
    if not extras:
        return question
    unique = list(dict.fromkeys(extras))
    return question + " " + " ".join(unique)


def retrieve_information(question, top_k=3):
    """Return relevant glossary entries and their local source labels."""
    if not isinstance(question, str) or not question.strip():
        return []

    expanded = _expand_question(question.strip())
    query_vector = _vectorizer.transform([expanded])
    similarities = cosine_similarity(query_vector, _matrix)[0]

    ranked = similarities.argsort()[::-1]
    results = []

    for index in ranked[:top_k]:
        score = float(similarities[index])

        if score <= 0:
            continue

        item = MEDICAL_KNOWLEDGE[index]

        results.append({
            "title": item["title"],
            "text": item["text"],
            "source": item["source"],
            "relevance": round(score, 3),
        })

    return results
