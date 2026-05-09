from src.dedupe import deduplicate_items, titles_similar
from src.utils import Item


def test_titles_similar_detects_near_duplicate():
    assert titles_similar("Measles outbreak in Texas expands", "Measles outbreak in Texas expands.")


def test_deduplicate_items_prefers_unique_url_and_title():
    items = [
        Item(title="A", source="s1", url="https://example.com/a?utm_source=x", category="c"),
        Item(title="A.", source="s2", url="https://example.com/a", category="c"),
        Item(title="B", source="s3", url="https://example.com/b", category="c"),
    ]
    result = deduplicate_items(items)
    assert len(result) == 2


def test_deduplicate_items_prefers_richer_duplicate():
    items = [
        Item(title="Measles update", source="Blog", url="https://example.com/a", category="c", summary="Short."),
        Item(
            title="Measles update.",
            source="CDC",
            url="https://example.com/b",
            category="c",
            summary="Longer official summary with more detail about the outbreak and response.",
            official=True,
        ),
    ]
    result = deduplicate_items(items)
    assert len(result) == 1
    assert result[0].source == "CDC"
