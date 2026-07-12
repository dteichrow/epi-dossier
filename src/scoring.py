from __future__ import annotations

import re

from .utils import Item
from .utils import has_disease_reference_signal


LOW_DETAIL_MARKERS = (
    "limited detail was available from feed metadata alone.",
    "limited usable detail remained after boilerplate cleanup.",
)

LOW_VALUE_TITLE_PATTERNS = (
    r"what (?:are|is) .*symptoms",
    r"what you need to know",
    r"here'?s what we know so far",
    r"latest updates?",
    r"live updates?",
)


def item_has_low_detail(item: Item) -> bool:
    summary = item.summary.lower().strip()
    return any(marker in summary for marker in LOW_DETAIL_MARKERS)


def is_regional_google_outbreak_lane(item: Item) -> bool:
    source = item.source.lower()
    return "google news" in source and any(
        label in source
        for label in (
            "africa outbreaks",
            "west africa outbreaks",
            "east africa outbreaks",
            "central africa outbreaks",
            "southern africa outbreaks",
            "south asia outbreaks",
            "southeast asia outbreaks",
            "latin america outbreaks",
            "rural outbreaks",
            "hemorrhagic fever and zoonoses",
            "ebola burial and treatment response",
        )
    )


def score_item(item: Item) -> int:
    score = 1
    source_lower = item.source.lower()
    reputable_google_signal = (
        "google news" in source_lower
        and item.publisher_tier in {"wire", "major_newsroom", "specialist_health"}
    )
    text = " ".join(
        [
            item.title.lower(),
            item.summary.lower(),
            item.category.lower(),
            source_lower,
        ]
    )

    if item.official:
        score += 2
    if item.publisher_tier in {"wire", "major_newsroom", "specialist_health"} and not item.official:
        score += 1
    if any(term in text for term in ("outbreak", "emerging", "cluster", "surveillance", "h5n1", "measles", "cholera", "dengue", "mpox", "marburg", "ebola", "anthrax", "nipah", "chikungunya", "yellow fever", "zika", "malaria", "meningococcal", "diphtheria", "pertussis", "legionnaires", "rabies", "hepatitis a", "norovirus", "cyclospora", "cyclosporiasis", "campylobacter", "shigella", "vibrio", "yersinia", "botulism", "oropouche", "rift valley fever", "mers", "avian influenza", "tuberculosis", "polio", "lassa")):
        score += 2
    if has_disease_reference_signal(text) and any(
        term in text
        for term in (
            "outbreak",
            "cluster",
            "confirmed",
            "suspected",
            "death",
            "deaths",
            "transmission",
            "health emergency",
            "case fatality",
            "contact tracing",
            "isolation",
            "treatment center",
            "treatment centre",
            "treatment facility",
            "clinic",
            "hospital",
            "ward",
            "safe burial",
            "traditional burial",
            "unsafe burial",
            "burial team",
            "body",
            "bodies",
            "retrieve body",
            "retrieve bodies",
            "body retrieval",
            "stormed",
            "burned",
            "burnt",
            "set on fire",
            "attack",
            "surveillance",
        )
    ):
        score += 2
    if any(term in text for term in ("africa", "uganda", "kenya", "tanzania", "ethiopia", "nigeria", "congo", "zimbabwe", "sudan", "india", "bangladesh", "pakistan", "sri lanka", "nepal", "cambodia", "vietnam", "thailand", "indonesia", "philippines")):
        score += 1
    if is_regional_google_outbreak_lane(item) and any(
        term in text
        for term in (
            "cholera",
            "dengue",
            "measles",
            "mpox",
            "marburg",
            "ebola",
            "anthrax",
            "lassa",
            "nipah",
            "chikungunya",
            "yellow fever",
            "zika",
            "malaria",
            "diphtheria",
            "pertussis",
            "rabies",
            "avian influenza",
            "h5n1",
            "polio",
            "tuberculosis",
            "health alert",
        )
    ):
        score += 1
    if reputable_google_signal and any(
        term in text
        for term in (
            "outbreak",
            "cluster",
            "surveillance",
            "hantavirus",
            "measles",
            "cholera",
            "cyclospora",
            "cyclosporiasis",
            "campylobacter",
            "shigella",
            "vibrio",
            "yersinia",
            "botulism",
            "dengue",
            "mpox",
            "marburg",
            "ebola",
            "anthrax",
            "nipah",
            "avian influenza",
            "h5n1",
            "polio",
            "tuberculosis",
        )
    ):
        score += 2
    if any(term in (item.source.lower(), (item.journal or "").lower()) for term in ("pubmed", "medrxiv", "biorxiv", "nejm", "lancet", "jama", "bmj", "nature", "science", "pnas")):
        score += 1
    if any(term in text for term in ("occupational", "worker", "niosh", "osha", "exposure", "environmental")):
        score += 1
    if any(
        term in text
        for term in (
            "ancient dna",
            "paleopathology",
            "historical epidemiology",
            "archaeology",
            "ancient pathogen",
            "archaeogenetics",
            "paleogenomics",
            "paleomicrobiology",
            "pathogen adna",
            "yersinia pestis",
            "variola",
            "mycobacterium leprae",
            "treponemal",
            "history of medicine",
        )
    ):
        score += 1
    if any(term in text for term in ("unusual", "weird", "historic", "reinterpretation", "spillover", "wastewater")):
        score += 1
    if len(item.summary) < 60 and not item.extracted_text:
        score -= 1
    if item_has_low_detail(item):
        if item.official:
            score -= 1
        elif is_regional_google_outbreak_lane(item):
            score -= 1
        else:
            score -= 2
    if "google news" in source_lower and item_has_low_detail(item) and not is_regional_google_outbreak_lane(item) and not reputable_google_signal:
        score -= 1
    if any(re.search(pattern, item.title, flags=re.IGNORECASE) for pattern in LOW_VALUE_TITLE_PATTERNS) and not item.official:
        score -= 2
    publication_types = [str(value).lower() for value in item.metadata.get("publication_types", [])]
    if any(term in publication_types for term in ("comment", "editorial", "news", "letter")) and not item.extracted_text:
        score -= 2
    if any(term in text for term in ("opinion", "commentary", "editorial")) and not item.official:
        score -= 2

    return max(1, min(score, 5))
