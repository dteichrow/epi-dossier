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


def test_fragile_official_sources_have_resilient_timeout_budgets():
    sources_by_name = {source.name: source for source in load_sources()}

    assert sources_by_name["WHO Regional Office for Africa"].timeout_seconds == 30
    assert sources_by_name["WHO Regional Office for Africa"].max_attempts == 2
    assert sources_by_name["USDA APHIS Avian Influenza"].timeout_seconds == 30
    assert sources_by_name["USDA APHIS Avian Influenza"].max_attempts == 2
    assert sources_by_name["Nigeria Centre for Disease Control"].type == "html_list"
    assert sources_by_name["Nigeria Centre for Disease Control"].url == "https://www.ncdc.gov.ng/news/press"
