from src.utils import load_sources


def test_source_config_includes_requested_official_state_and_cdc_sources():
    names = {source.name for source in load_sources()}

    assert "CDC Current Outbreak List" in names
    assert "California Department of Public Health News" in names
    assert "New York State Department of Health Press Releases" in names
    assert "Florida Department of Health Press Releases" in names
    assert "Texas Department of State Health Services News" in names
    assert "Washington State Department of Health Newsroom" in names
    assert "Oregon Health Authority News Releases" in names
