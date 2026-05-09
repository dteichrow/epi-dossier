from __future__ import annotations

from difflib import SequenceMatcher

from .utils import Item, canonicalize_url, clean_headline, normalize_whitespace


def titles_similar(left: str, right: str, threshold: float = 0.92) -> bool:
    left_clean = clean_headline(left).lower()
    right_clean = clean_headline(right).lower()
    ratio = SequenceMatcher(None, left_clean, right_clean).ratio()
    if ratio >= threshold:
        return True
    left_tokens = {token for token in left_clean.split() if len(token) > 3}
    right_tokens = {token for token in right_clean.split() if len(token) > 3}
    if not left_tokens or not right_tokens:
        return False
    overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    return overlap >= 0.7


def deduplicate_items(items: list[Item]) -> list[Item]:
    unique: list[Item] = []
    seen_urls: set[str] = set()
    for item in items:
        canonical = canonicalize_url(item.url)
        if canonical in seen_urls:
            continue
        replaced = False
        for index, existing in enumerate(unique):
            if not titles_similar(item.title, existing.title):
                continue
            if item_quality(item) > item_quality(existing):
                unique[index] = item
            replaced = True
            break
        if replaced:
            continue
        seen_urls.add(canonical)
        unique.append(item)
    return unique


def item_quality(item: Item) -> tuple[int, int, int]:
    return (
        1 if item.official else 0,
        len(normalize_whitespace(item.summary or item.extracted_text)),
        1 if item.published_at else 0,
    )
