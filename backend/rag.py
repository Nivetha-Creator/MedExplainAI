
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


MEDICAL_KNOWLEDGE = [
    {
        "title": "Laboratory reference ranges",
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
        "text": (
            "Haemoglobin is a protein in red blood cells that carries "
            "oxygen. Haemoglobin results need to be interpreted using "
            "the laboratory's range and the person's clinical context."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "White blood cells",
        "text": (
            "White blood cells are part of the immune system. Their "
            "count can change for many reasons. A white blood cell "
            "result alone cannot identify the cause of a change."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Platelets",
        "text": (
            "Platelets are blood components that help form clots. "
            "Platelet counts should be interpreted with the reported "
            "reference interval and relevant clinical information."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Blood glucose",
        "text": (
            "Blood glucose measures the amount of glucose in the blood. "
            "Interpretation depends on the test type, timing, units, "
            "laboratory range, and clinical context."
        ),
        "source": "MedExplain educational glossary",
    },
    {
        "title": "Creatinine",
        "text": (
            "Creatinine is a waste product measured in blood or urine. "
            "Blood creatinine can help assess kidney function, but "
            "interpretation may require other results and clinical context."
        ),
        "source": "MedExplain educational glossary",
    },
]


_documents = [
    item["title"] + ". " + item["text"]
    for item in MEDICAL_KNOWLEDGE
]

_vectorizer = TfidfVectorizer(stop_words="english")
_matrix = _vectorizer.fit_transform(_documents)


def retrieve_information(question, top_k=3):
    """Return relevant glossary entries and their local source labels."""
    if not question or not question.strip():
        return []

    query_vector = _vectorizer.transform([question])
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
