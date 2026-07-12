from __future__ import annotations

import re
from collections.abc import Iterable

from .parsers import clean_extracted_text, is_boilerplate
from .utils import Item, normalize_whitespace


GENERIC_SENTENCE_PATTERNS = (
    r"here'?s what we know so far",
    r"what you need to know",
    r"breaking news",
    r"latest news",
    r"watch live",
    r"click here",
)

ACTION_TERMS = (
    "reported",
    "investigation",
    "investigating",
    "monitoring",
    "confirmed",
    "suspected",
    "quarantined",
    "evacuated",
    "identified",
    "advised",
    "announced",
    "warned",
    "detected",
    "sequenced",
    "linked",
    "associated",
)

SIGNAL_TERMS = (
    "death",
    "deaths",
    "died",
    "fatal",
    "case",
    "cases",
    "outbreak",
    "cluster",
    "transmission",
    "human-to-human",
    "wastewater",
    "vaccine",
    "surveillance",
    "risk",
)

AGENCY_TERMS = ("cdc", "ecdc", "who", "fda", "aphis", "department of health", "mmwr")
LOCATION_TERMS = ("ship", "county", "state", "province", "country", "coast", "aboard", "port", "hospital")


def split_sentences(text: str) -> list[str]:
    normalized = normalize_whitespace(text)
    if not normalized:
        return []
    return [normalize_whitespace(chunk) for chunk in re.split(r"(?<=[.!?])\s+", normalized) if normalize_whitespace(chunk)]


def summarize_item(item: Item) -> Item:
    if item.metadata.get("preserve_source_summary") and item.summary:
        item.summary = normalize_whitespace(item.summary)
    else:
        summary_sentences = build_fact_summary_sentences(item, max_sentences=3)
        item.summary = " ".join(summary_sentences) if summary_sentences else low_detail_summary(item)
    item.why_it_matters = build_why_it_matters(item)
    item.caveats = build_caveats(item)
    return item


def build_fact_summary_sentences(item: Item, max_sentences: int = 3) -> list[str]:
    candidates = candidate_sentences_for_item(item)
    ranked = rank_sentences(candidates, title=item.title)
    selected: list[str] = []
    for sentence in ranked:
        if is_redundant_against_selected(sentence, selected):
            continue
        selected.append(sentence)
        if len(selected) >= max_sentences:
            break
    return selected


def candidate_sentences_for_item(item: Item) -> list[str]:
    pools: list[str] = []
    if item.extracted_text:
        pools.append(item.extracted_text)
    if item.summary:
        pools.append(item.summary)
    unique: list[str] = []
    seen: set[str] = set()
    for pool in pools:
        for sentence in split_sentences(clean_extracted_text(pool)):
            cleaned = clean_sentence(sentence)
            if not cleaned:
                continue
            normalized = cleaned.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            unique.append(cleaned)
    return unique


def clean_sentence(sentence: str) -> str:
    cleaned = normalize_whitespace(sentence)
    cleaned = re.sub(
        r"\s*[-|]\s*(reuters|associated press|ap|yahoo|msn|aol\.com|abc news|nbc news|fox news|sky news|newsnation|ndtv|wfla|kcra|welcome to the united nations)$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+(welcome to the united nations)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = normalize_whitespace(cleaned)
    if len(cleaned) < 30:
        return ""
    return cleaned


def rank_sentences(sentences: Iterable[str], title: str) -> list[str]:
    scored: list[tuple[int, str]] = []
    for sentence in sentences:
        if sentence_should_drop(sentence, title):
            continue
        scored.append((score_sentence(sentence, title), sentence))
    scored.sort(key=lambda pair: (pair[0], len(pair[1])), reverse=True)
    return [sentence for _, sentence in scored]


def sentence_should_drop(sentence: str, title: str) -> bool:
    lowered = sentence.lower()
    if is_boilerplate(lowered):
        return True
    if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in GENERIC_SENTENCE_PATTERNS):
        return True
    if title_overlap_ratio(sentence, title) >= 0.72:
        return True
    if looks_like_headline_bundle(sentence):
        return True
    if sentence_just_repeats_title_plus_outlet(sentence, title):
        return True
    return False


def score_sentence(sentence: str, title: str) -> int:
    lowered = sentence.lower()
    score = 0
    score += 4 * len(re.findall(r"\b\d+\b", sentence))
    score += 4 * sum(term in lowered for term in ("death", "deaths", "died", "fatal", "quarantine", "quarantined", "evacuated", "evacuation"))
    score += 3 * sum(term in lowered for term in ("human-to-human", "person-to-person", "under investigation", "risk", "surveillance", "wastewater"))
    score += 2 * sum(term in lowered for term in ACTION_TERMS)
    score += 2 * sum(term in lowered for term in SIGNAL_TERMS)
    score += 1 * sum(term in lowered for term in AGENCY_TERMS)
    score += 1 * sum(term in lowered for term in LOCATION_TERMS)
    score += 2 if title_overlap_ratio(sentence, title) <= 0.45 else 0
    score -= 2 if len(sentence.split()) > 40 else 0
    return score


def is_redundant_against_selected(candidate: str, selected: list[str]) -> bool:
    candidate_tokens = content_tokens(candidate)
    if not candidate_tokens:
        return True
    for prior in selected:
        overlap = overlap_ratio(candidate_tokens, content_tokens(prior))
        if overlap >= 0.65:
            return True
    return False


def low_detail_summary(item: Item) -> str:
    if item.extracted_text:
        return "Limited usable detail remained after boilerplate cleanup."
    if item.summary and not sentence_just_repeats_title_plus_outlet(item.summary, item.title):
        return trim_text(clean_extracted_text(item.summary), 180) or "Limited detail was available from feed metadata alone."
    return "Limited detail was available from feed metadata alone."


def build_why_it_matters(item: Item) -> str:
    lowered = f"{item.title} {item.summary} {item.category}".lower()
    why_parts: list[str] = []
    if any(term in lowered for term in ("outbreak", "cluster", "surveillance", "h5n1", "measles", "dengue", "mpox", "cholera", "hantavirus")):
        why_parts.append("Directly relevant to outbreak detection, transmission monitoring, or response.")
    if item.official:
        why_parts.append("Comes from an official or primary-source channel.")
    if any(term in lowered for term in ("occupational", "worker", "exposure", "niosh", "osha")):
        why_parts.append("Useful for occupational or environmental epidemiology coverage.")
    if any(term in lowered for term in ("ancient", "historical", "paleopathology")):
        why_parts.append("Useful for historical epidemiology or paleopathology coverage.")
    return " ".join(why_parts[:2]) or "Relevant because it may change surveillance interpretation or public-health framing."


def build_caveats(item: Item) -> str:
    caveats: list[str] = []
    if item.source_type in {"medrxiv", "biorxiv"}:
        caveats.append("Preprint; findings may change before peer review.")
    if "limited usable detail remained" in item.summary.lower() or "limited detail was available" in item.summary.lower():
        caveats.append("Usable source detail was limited after cleanup.")
    if not item.published_at:
        caveats.append("Publication timestamp was not reliably available.")
    return " ".join(caveats) or "Summary stays within source text and metadata; no outside facts were added."


def content_tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 3}


def overlap_ratio(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def title_overlap_ratio(sentence: str, title: str) -> float:
    return overlap_ratio(content_tokens(sentence), content_tokens(title))


def looks_like_headline_bundle(text: str) -> bool:
    words = text.split()
    if len(words) < 6:
        return False
    if len(re.findall(r"[A-Z][a-z]+", text)) >= max(6, len(words) // 2):
        return True
    return text.endswith(("Yahoo", "MSN", "AOL.com", "ABC News", "NBC News", "Fox News", "Sky News"))


def sentence_just_repeats_title_plus_outlet(sentence: str, title: str) -> bool:
    stripped = normalize_whitespace(sentence)
    title_clean = normalize_whitespace(title)
    stripped_alnum = re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip()
    title_alnum = re.sub(r"[^a-z0-9]+", " ", title_clean.lower()).strip()
    if stripped_alnum == title_alnum:
        return True
    if stripped_alnum.startswith(title_alnum):
        tail = stripped_alnum[len(title_alnum):].strip()
        if tail and (len(tail.split()) <= 5 or tail in {"welcome to the united nations"}):
            return True
    return False


def trim_text(text: str, max_length: int) -> str:
    text = normalize_whitespace(text)
    if len(text) <= max_length:
        return text
    shortened = text[: max_length - 3].rsplit(" ", 1)[0]
    return shortened + "..."
