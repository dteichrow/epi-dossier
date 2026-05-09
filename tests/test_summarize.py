from src.summarize import build_fact_summary_sentences, summarize_item
from src.utils import Item


def test_build_fact_summary_sentences_drops_title_and_outlet_echo():
    item = Item(
        title="Human-to-human transmission suspected in hantavirus outbreak on cruise ship",
        source="Google News Outbreaks",
        url="https://example.com/a",
        category="Outbreaks and emerging infections",
        summary="Human-to-human transmission suspected in hantavirus outbreak on cruise ship NBC News",
        extracted_text=(
            "Officials investigating the cruise ship outbreak said three deaths have been reported. "
            "Passengers with symptoms were quarantined as the ship remained offshore."
        ),
    )

    sentences = build_fact_summary_sentences(item, max_sentences=2)
    joined = " ".join(sentences)
    assert "NBC News" not in joined
    assert "three deaths" in joined.lower()
    assert "quarantined" in joined.lower()


def test_summarize_item_prefers_concrete_facts_over_generic_context():
    item = Item(
        title="Suspected hantavirus outbreak on cruise ship under investigation: risk for Europeans very low",
        source="ECDC News",
        url="https://example.com/b",
        category="Outbreaks and emerging infections",
        extracted_text=(
            "A cluster of severe acute respiratory illness, including three deaths and one severely ill individual, has been reported among passengers. "
            "The ship is currently located off the coast of Cabo Verde, with 149 people on board. "
            "ECDC said risk for Europeans is currently very low."
        ),
        official=True,
    )
    summarize_item(item)
    assert "three deaths" in item.summary.lower()
    assert "cabo verde" in item.summary.lower()
    assert item.summary.lower() != item.title.lower()


def test_build_fact_summary_sentences_drops_united_nations_suffix_wrapper():
    item = Item(
        title="WHO leads response to cruise ship hantavirus outbreak",
        source="Google News Outbreaks",
        url="https://example.com/un-wrapper",
        category="Outbreaks and emerging infections",
        summary="WHO leads response to cruise ship hantavirus outbreak Welcome to the United Nations",
    )

    sentences = build_fact_summary_sentences(item, max_sentences=2)
    assert sentences == []
    summarize_item(item)
    assert item.summary == "Limited detail was available from feed metadata alone."
