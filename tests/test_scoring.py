from src.scoring import score_item
from src.utils import Item


def test_score_item_caps_at_five():
    item = Item(
        title="Official measles outbreak surveillance update with occupational exposure and ancient pathogen context",
        source="CDC",
        url="https://example.com",
        category="Historical epidemiology / ancient disease / paleopathology",
        summary="Outbreak surveillance with H5N1 wastewater occupational exposure and ancient DNA pathogen detail.",
        official=True,
        journal="NEJM",
    )
    assert score_item(item) == 5
