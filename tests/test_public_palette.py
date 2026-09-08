from src.rebuild_public import refresh_archived_palette
from src.render_art import THEMES
from src.render_site import base_styles


def test_archived_style_refresh_keeps_reporting_and_opacity():
    text = "<style>.badge {color:#35552B;background:rgba(60, 88, 48,0.12)}</style><p>Published 2026-03-02. Green County: 0 cases.</p>"
    refreshed = refresh_archived_palette(text)
    assert "#61436e" in refreshed
    assert "rgba(97,67,110,0.12)" in refreshed
    assert "Published 2026-03-02. Green County: 0 cases." in refreshed
    assert refresh_archived_palette(refreshed) == refreshed


def test_current_newsdesk_styles_and_vector_art_use_plum():
    assert "#35552b" not in base_styles()
    assert THEMES["vector"]["bg_a"] == "#30233c"
