import requests
from datetime import date
from unittest.mock import Mock

from src.fetchers import (
    BROWSERISH_HEADERS,
    CachedHTTPResponse,
    decode_google_news_batchexecute,
    enrich_item_text,
    extract_google_news_decode_params,
    extract_google_news_embedded_urls,
    fetch_all_sources,
    fetch_html_list,
    fetch_pubmed,
    fetch_rss,
    resilient_get,
)
from src.utils import Item, SourceConfig


def test_fetch_rss_parses_entries(monkeypatch):
    xml = """
    <rss version="2.0">
      <channel>
        <title>Test</title>
        <item>
          <title>Test outbreak</title>
          <link>https://example.com/a</link>
          <pubDate>Sun, 03 May 2026 10:00:00 GMT</pubDate>
          <description>Outbreak detail</description>
          <source url="https://www.reuters.com">Reuters</source>
        </item>
      </channel>
    </rss>
    """
    response = Mock()
    response.text = xml
    response.raise_for_status = Mock()
    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: response)

    source = SourceConfig(name="Test RSS", type="rss", category="Outbreaks", url="https://example.com/feed.xml")
    items = fetch_rss(source, logger=Mock())
    assert len(items) == 1
    assert items[0].title == "Test outbreak"
    assert items[0].publisher == "Reuters"


def test_fetch_rss_normalizes_escaped_query_separator(monkeypatch):
    xml = """
    <rss version="2.0">
      <channel>
        <title>Test</title>
        <item>
          <title>ABC outbreak report</title>
          <link>https://abcnews.com/International/example/story?id\\=133061121</link>
          <description>Outbreak detail</description>
        </item>
      </channel>
    </rss>
    """
    response = Mock()
    response.text = xml
    response.raise_for_status = Mock()
    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: response)

    source = SourceConfig(name="Test RSS", type="rss", category="Outbreaks", url="https://example.com/feed.xml")
    items = fetch_rss(source, logger=Mock())

    assert items[0].url == "https://abcnews.com/International/example/story?id=133061121"
    assert items[0].metadata["raw_url"] == "https://abcnews.com/International/example/story?id=133061121"


def test_fetch_html_list_drops_generic_anchor_titles(monkeypatch):
    html = """
    <html>
      <body>
        <a href="/a">See</a>
        <a href="/b">Outbreak investigation: Salmonella in cucumbers</a>
      </body>
    </html>
    """
    response = Mock()
    response.text = html
    response.raise_for_status = Mock()
    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: response)

    source = SourceConfig(
        name="Test HTML",
        type="html_list",
        category="Outbreaks",
        url="https://example.com/page",
        item_selector="a",
    )
    items = fetch_html_list(source, logger=Mock())
    assert len(items) == 1
    assert items[0].title == "Outbreak investigation: Salmonella in cucumbers"


def test_fetch_html_list_parses_fda_outbreak_rows(monkeypatch):
    html = """
    <html>
      <head>
        <meta property="article:modified_time" content="2026-05-05T11:14:00+00:00" />
      </head>
      <body>
        <table>
          <thead>
            <tr>
              <th>Date Posted</th><th>Reference #</th><th>Pathogen</th><th>Product</th><th>Total Case Count</th>
              <th>Investigation Status</th><th>Outbreak/Event Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>3/16/2026</td>
              <td>1369</td>
              <td>E. coli O157:H7</td>
              <td>Raw Cheddar Cheese</td>
              <td>12</td>
              <td>Active</td>
              <td>Ongoing</td>
              <td><a href="/food/outbreaks-foodborne-illness/outbreak-investigation-e-coli-o157h7-raw-cheddar-cheese-march-2026">See Advisory</a></td>
            </tr>
          </tbody>
        </table>
      </body>
    </html>
    """
    response = Mock()
    response.text = html
    response.raise_for_status = Mock()
    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: response)

    source = SourceConfig(
        name="FDA Foodborne Outbreaks",
        type="html_list",
        category="Outbreaks",
        url="https://www.fda.gov/food/outbreaks-foodborne-illness/investigations-foodborne-illness-outbreaks",
        official=True,
        max_items=10,
    )
    items = fetch_html_list(source, logger=Mock())
    assert len(items) == 1
    assert items[0].url.endswith("outbreak-investigation-e-coli-o157h7-raw-cheddar-cheese-march-2026")
    assert "1369" in items[0].title
    assert "Reported total case count: 12." in items[0].summary


def test_fetch_html_list_parses_ncdc_press_rows(monkeypatch):
    html = """
    <section id="news">
      <article>
        <h3>National Public Health Advisory on State Preparedness for Bundibugyo Ebola Virus Disease</h3>
        <h4>Thu 28 May 2026</h4>
        NCDC advises state health authorities to prepare for the evolving regional outbreak.
      </article>
      <a href="/news/537/national-public-health-advisory">Read more</a>
    </section>
    """
    response = Mock()
    response.text = html
    response.raise_for_status = Mock()
    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: response)

    source = SourceConfig(
        name="Nigeria Centre for Disease Control",
        type="html_list",
        category="Outbreaks and emerging infections",
        url="https://www.ncdc.gov.ng/news/press",
        official=True,
        item_selector="#news article",
        max_items=10,
    )
    items = fetch_html_list(source, logger=Mock())

    assert len(items) == 1
    assert items[0].title.startswith("National Public Health Advisory")
    assert items[0].url == "https://www.ncdc.gov.ng/news/537/national-public-health-advisory"
    assert items[0].published_at is not None


def test_fetch_html_list_honors_source_ssl_and_timeout_settings(monkeypatch):
    response = Mock()
    response.text = "<html><body><a href='/a'>Test outbreak item</a></body></html>"
    response.raise_for_status = Mock()
    captured: dict[str, object] = {}

    def fake_get(*args, **kwargs):
        captured.update(kwargs)
        return response

    monkeypatch.setattr("src.fetchers.requests.get", fake_get)

    source = SourceConfig(
        name="SSL Edge Case Source",
        type="html_list",
        category="Outbreaks",
        url="https://example.com/page",
        item_selector="a",
        timeout_seconds=8,
        max_attempts=1,
        verify_ssl=False,
    )
    items = fetch_html_list(source, logger=Mock())
    assert len(items) == 1
    assert captured["timeout"] == 8
    assert captured["verify"] is False
    assert captured["headers"] == BROWSERISH_HEADERS


def test_fetch_pubmed_uses_efetch_abstract_and_doi(monkeypatch):
    search_response = Mock()
    search_response.json = Mock(return_value={"esearchresult": {"idlist": ["42083789"]}})
    search_response.raise_for_status = Mock()

    summary_response = Mock()
    summary_response.json = Mock(
        return_value={
            "result": {
                "42083789": {
                    "title": "A copper uptake ABC transport system is essential for Mycobacterium tuberculosis virulence.",
                    "pubdate": "2026 May 05",
                    "authors": [{"name": "Xu Z"}, {"name": "Tang H"}],
                    "fulljournalname": "Emerging microbes & infections",
                }
            }
        }
    )
    summary_response.raise_for_status = Mock()

    detail_response = Mock()
    detail_response.text = """
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>42083789</PMID>
          <Article>
            <Journal>
              <JournalIssue><PubDate><Year>2026</Year><Month>May</Month><Day>05</Day></PubDate></JournalIssue>
              <Title>Emerging microbes &amp; infections</Title>
            </Journal>
            <ArticleTitle>A copper uptake ABC transport system is essential for Mycobacterium tuberculosis virulence.</ArticleTitle>
            <ELocationID EIdType="doi">10.1080/22221751.2026.2668753</ELocationID>
            <Abstract>
              <AbstractText>Deletion of the transporter lowered bacterial burdens in a murine model.</AbstractText>
            </Abstract>
            <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
            <ArticleDate><Year>2026</Year><Month>05</Month><Day>05</Day></ArticleDate>
          </Article>
        </MedlineCitation>
        <PubmedData><PublicationStatus>aheadofprint</PublicationStatus></PubmedData>
      </PubmedArticle>
    </PubmedArticleSet>
    """
    detail_response.raise_for_status = Mock()

    responses = iter([search_response, summary_response, detail_response])
    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: next(responses))

    source = SourceConfig(
        name="PubMed Infectious Disease Search",
        type="pubmed",
        category="Major epidemiology studies",
        official=True,
        search="tuberculosis",
        max_items=5,
    )
    items = fetch_pubmed(source, logger=Mock(), start_date=date(2026, 5, 4), end_date=date(2026, 5, 5))
    assert len(items) == 1
    assert items[0].doi == "10.1080/22221751.2026.2668753"
    assert "murine model" in items[0].summary.lower()
    assert items[0].extracted_text
    assert items[0].metadata["publication_status"] == "aheadofprint"


def test_fetch_pubmed_comment_record_uses_clean_fallback_summary(monkeypatch):
    search_response = Mock()
    search_response.json = Mock(return_value={"esearchresult": {"idlist": ["42081432"]}})
    search_response.raise_for_status = Mock()

    summary_response = Mock()
    summary_response.json = Mock(
        return_value={
            "result": {
                "42081432": {
                    "title": "Editorial Note: Immuno-PCR - A New Tool for Paleomicrobiology: The Plague Paradigm.",
                    "pubdate": "2026",
                    "authors": [{"name": "PLOS One Editors"}],
                    "fulljournalname": "PloS one",
                }
            }
        }
    )
    summary_response.raise_for_status = Mock()

    detail_response = Mock()
    detail_response.text = """
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>42081432</PMID>
          <Article>
            <Journal><JournalIssue><PubDate><Year>2026</Year></PubDate></JournalIssue><Title>PloS one</Title></Journal>
            <ArticleTitle>Editorial Note: Immuno-PCR - A New Tool for Paleomicrobiology: The Plague Paradigm.</ArticleTitle>
            <ELocationID EIdType="doi">10.1371/journal.pone.0348536</ELocationID>
            <PublicationTypeList>
              <PublicationType>Journal Article</PublicationType>
              <PublicationType>Comment</PublicationType>
            </PublicationTypeList>
          </Article>
          <CommentsCorrectionsList>
            <CommentsCorrections RefType="CommentOn">
              <RefSource>PLoS One. 2012;7(2):e31744. doi: 10.1371/journal.pone.0031744.</RefSource>
            </CommentsCorrections>
          </CommentsCorrectionsList>
        </MedlineCitation>
        <PubmedData><PublicationStatus>epublish</PublicationStatus></PubmedData>
      </PubmedArticle>
    </PubmedArticleSet>
    """
    detail_response.raise_for_status = Mock()

    responses = iter([search_response, summary_response, detail_response])
    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: next(responses))

    source = SourceConfig(
        name="PubMed Historical Epidemiology",
        type="pubmed",
        category="Historical epidemiology / ancient disease / paleopathology",
        official=True,
        search="paleomicrobiology",
        max_items=5,
    )
    items = fetch_pubmed(source, logger=Mock(), start_date=date(2026, 5, 4), end_date=date(2026, 5, 5))
    assert len(items) == 1
    assert "publication type: journal article, comment." in items[0].summary.lower()
    assert "10.1371/journal.pone.0031744" not in items[0].summary


def test_enrich_item_text_resolves_google_news_canonical_url(monkeypatch):
    response = Mock()
    response.text = """
    <html>
      <head>
        <link rel="canonical" href="https://www.nbcnews.com/health/health-news/hantavirus-cruise-outbreak-rcna99999" />
      </head>
      <body>
        <p>Three passengers were evacuated from the cruise ship after the outbreak expanded.</p>
      </body>
    </html>
    """
    response.headers = {"content-type": "text/html"}
    response.url = "https://news.google.com/rss/articles/example"
    response.raise_for_status = Mock()
    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: response)

    item = Item(
        title="Hantavirus cruise outbreak: Three passengers evacuated",
        source="Google News Outbreaks",
        url="https://news.google.com/rss/articles/example",
        category="Outbreaks and emerging infections",
        summary="Limited detail was available from feed metadata alone.",
        source_type="rss",
    )
    enriched = enrich_item_text(item, logger=Mock())
    assert enriched.url == "https://www.nbcnews.com/health/health-news/hantavirus-cruise-outbreak-rcna99999"
    assert "evacuated" in enriched.extracted_text.lower()


def test_enrich_item_text_recovers_embedded_publisher_url_from_google_news_html(monkeypatch):
    response = Mock()
    response.text = """
    <html>
      <head></head>
      <body>
        <script>
          window.__STATE__ = {"targetUrl":"https:\\/\\/www.nytimes.com\\/2026\\/05\\/07\\/world\\/europe\\/hantavirus-cruise-ship-outbreak.html"};
        </script>
        <p>Google wrapper page.</p>
      </body>
    </html>
    """
    response.headers = {"content-type": "text/html"}
    response.url = "https://news.google.com/rss/articles/example-2"
    response.raise_for_status = Mock()
    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: response)

    item = Item(
        title="Cruise Ship Struck by Hantavirus Is to Head to Canary Islands, W.H.O. Says",
        source="Google News Major Outbreak Desks",
        url="https://news.google.com/rss/articles/example-2",
        category="Outbreaks and emerging infections",
        summary="Limited detail was available from feed metadata alone.",
        source_type="rss",
    )
    enriched = enrich_item_text(item, logger=Mock())
    assert enriched.url == "https://www.nytimes.com/2026/05/07/world/europe/hantavirus-cruise-ship-outbreak.html"


def test_extract_google_news_embedded_urls_ignores_svg_namespace_url():
    document = """
    <html>
      <body>
        <svg xmlns="http://www.w3.org/2000/svg"></svg>
        <a href="https://angular.dev/license">Angular license</a>
        <script src="https://www.google-analytics.com/analytics.js"></script>
        <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Google+Sans+Text:400,500,700">
        <script>
          window.__STATE__ = {"targetUrl":"https:\\/\\/www.palmbeachpost.com\\/story\\/news\\/health-care\\/2026\\/05\\/07\\/measles-florida-cases\\/123456789\\/"};
        </script>
      </body>
    </html>
    """

    urls = extract_google_news_embedded_urls(document)

    assert "http://www.w3.org/2000/svg" not in urls
    assert "https://angular.dev/license" not in urls
    assert "https://www.google-analytics.com/analytics.js" not in urls
    assert "https://fonts.googleapis.com/css?family=Google+Sans+Text:400,500,700" not in urls
    assert urls == ["https://www.palmbeachpost.com/story/news/health-care/2026/05/07/measles-florida-cases/123456789/"]


def test_extract_google_news_embedded_urls_prioritizes_known_major_publishers():
    document = """
    <html>
      <body>
        <script>
          window.__STATE__ = {
            "candidateA":"https:\\/\\/random-example.org\\/tracking\\/story-123",
            "candidateB":"https:\\/\\/www.reuters.com\\/world\\/europe\\/hantavirus-update-2026-05-08\\/",
            "candidateC":"https:\\/\\/www.bbc.com\\/news\\/world-europe-12345678"
          };
        </script>
      </body>
    </html>
    """

    urls = extract_google_news_embedded_urls(document)

    assert urls[0].startswith("https://www.reuters.com/")
    assert urls[1].startswith("https://www.bbc.com/")


def test_extract_google_news_embedded_urls_unwraps_google_redirect_targets():
    document = """
    <html>
      <body>
        <a href="https://www.google.com/url?url=https%3A%2F%2Fwww.theguardian.com%2Fworld%2F2026%2Fmay%2F08%2Fhantavirus-outbreak-update&amp;sa=D">Guardian redirect</a>
        <script>
          window.__STATE__ = {
            "candidate":"https://www.google.com/url?url=https%3A%2F%2Fwww.reuters.com%2Fworld%2Feurope%2Fhantavirus-update-2026-05-08%2F&sa=D"
          };
        </script>
      </body>
    </html>
    """

    urls = extract_google_news_embedded_urls(document)

    assert "https://www.reuters.com/world/europe/hantavirus-update-2026-05-08/" in urls
    assert "https://www.theguardian.com/world/2026/may/08/hantavirus-outbreak-update" in urls
    assert urls[0].startswith("https://www.reuters.com/")


def test_extract_google_news_embedded_urls_prefers_article_like_paths_over_homepages():
    document = """
    <html>
      <body>
        <script>
          window.__STATE__ = {
            "homepage":"https:\\/\\/www.nytimes.com\\/",
            "article":"https:\\/\\/www.nytimes.com\\/2026\\/05\\/08\\/world\\/europe\\/hantavirus-cruise-update.html"
          };
        </script>
      </body>
    </html>
    """

    urls = extract_google_news_embedded_urls(document)

    assert urls[0] == "https://www.nytimes.com/2026/05/08/world/europe/hantavirus-cruise-update.html"


def test_extract_google_news_decode_params_reads_timestamp_and_signature():
    document = """
    <html>
      <body>
        <div data-n-a-ts="1778270900" data-n-a-sg="AaLI4RTbcuShbysc0Xa9-x_AvGxR"></div>
      </body>
    </html>
    """

    params = extract_google_news_decode_params(
        document,
        "https://news.google.com/rss/articles/CBMisgFBVV95cUxNa3k5SnotMkxUUlJuVVBRRVJuQkgwOTJRS3MzZ1oxbi0xUHFaM1BjTVd1dlUyellnSndqaHdFWXMxMnAyRnViVmlXVFhIMXludzhraVJIVmtSODFEUWtsaTNpLVpGNXhiaTJwc0lVOTJKaFhrNnpHaVFqVXBWUUtDc0cxamlYdGdDNmZPaTV6aW9aS0ZiTXFIVzhLeE5tM2pPRmkzdzl6ZWtaVUhiQm1OcExR?oc=5",
    )

    assert params == (
        "CBMisgFBVV95cUxNa3k5SnotMkxUUlJuVVBRRVJuQkgwOTJRS3MzZ1oxbi0xUHFaM1BjTVd1dlUyellnSndqaHdFWXMxMnAyRnViVmlXVFhIMXludzhraVJIVmtSODFEUWtsaTNpLVpGNXhiaTJwc0lVOTJKaFhrNnpHaVFqVXBWUUtDc0cxamlYdGdDNmZPaTV6aW9aS0ZiTXFIVzhLeE5tM2pPRmkzdzl6ZWtaVUhiQm1OcExR",
        "1778270900",
        "AaLI4RTbcuShbysc0Xa9-x_AvGxR",
    )


def test_decode_google_news_batchexecute_extracts_direct_url(monkeypatch):
    response = Mock()
    response.text = ')]}\'\\n\\n[["wrb.fr","Fbv4je","[\\\\\\"garturlres\\\\\\",\\\\\\"https://news.sky.com/story/hantavirus-update-123\\\\\\",1]",null,null,null,"generic"]]'
    response.raise_for_status = Mock()
    monkeypatch.setattr("src.fetchers.requests.post", lambda *args, **kwargs: response)

    decoded = decode_google_news_batchexecute(
        "CBMisgFBVV95cUxNa3k5SnotMkxUUlJuVVBRRVJuQkgwOTJRS3MzZ1oxbi0xUHFaM1BjTVd1dlUyellnSndqaHdFWXMxMnAyRnViVmlXVFhIMXludzhraVJIVmtSODFEUWtsaTNpLVpGNXhiaTJwc0lVOTJKaFhrNnpHaVFqVXBWUUtDc0cxamlYdGdDNmZPaTV6aW9aS0ZiTXFIVzhLeE5tM2pPRmkzdzl6ZWtaVUhiQm1OcExR",
        "1778270900",
        "AaLI4RTbcuShbysc0Xa9-x_AvGxR",
        logger=Mock(),
    )

    assert decoded == "https://news.sky.com/story/hantavirus-update-123"


def test_enrich_item_text_uses_batchexecute_when_google_wrapper_page_has_decode_keys(monkeypatch):
    get_response = Mock()
    get_response.text = """
    <html>
      <head></head>
      <body>
        <div data-n-a-ts="1778270900" data-n-a-sg="AaLI4RTbcuShbysc0Xa9-x_AvGxR"></div>
        <p>Google wrapper page.</p>
      </body>
    </html>
    """
    get_response.headers = {"content-type": "text/html"}
    get_response.url = "https://news.google.com/rss/articles/example-4"
    get_response.raise_for_status = Mock()

    post_response = Mock()
    post_response.text = ')]}\'\\n\\n[["wrb.fr","Fbv4je","[\\\\\\"garturlres\\\\\\",\\\\\\"https://www.bbc.com/news/world-europe-12345678\\\\\\",1]",null,null,null,"generic"]]'
    post_response.raise_for_status = Mock()

    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: get_response)
    monkeypatch.setattr("src.fetchers.requests.post", lambda *args, **kwargs: post_response)

    item = Item(
        title="BBC follow-up",
        source="Google News Major Outbreak Desks",
        url="https://news.google.com/rss/articles/example-4",
        category="Outbreaks and emerging infections",
        summary="Limited detail was available from feed metadata alone.",
        source_type="rss",
    )
    enriched = enrich_item_text(item, logger=Mock())

    assert enriched.url == "https://www.bbc.com/news/world-europe-12345678"


def test_enrich_item_text_does_not_refetch_failed_google_news_wrapper(monkeypatch):
    call_count = {"value": 0}

    def fake_get(*args, **kwargs):
        call_count["value"] += 1
        raise requests.ConnectionError("DNS failure")

    monkeypatch.setattr("src.fetchers.requests.get", fake_get)

    item = Item(
        title="Wrapper-only item",
        source="Google News Outbreaks",
        url="https://news.google.com/rss/articles/example-3",
        category="Outbreaks and emerging infections",
        summary="Limited detail was available from feed metadata alone.",
        source_type="rss",
    )
    enriched = enrich_item_text(item, logger=Mock())

    assert enriched.url == "https://news.google.com/rss/articles/example-3"
    assert enriched.extracted_text == ""
    assert call_count["value"] == 1


def test_resilient_get_uses_recent_cache_after_429(monkeypatch, tmp_path):
    monkeypatch.setattr("src.fetchers.HTTP_CACHE_DIR", tmp_path / "http_cache")
    monkeypatch.setattr("src.fetchers.time.sleep", lambda *_args, **_kwargs: None)

    success = Mock()
    success.status_code = 200
    success.url = "https://example.com/feed"
    success.text = '{"ok": true}'
    success.headers = {"content-type": "application/json"}
    success.raise_for_status = Mock()

    retry_response = Mock()
    retry_response.status_code = 429
    retry_response.headers = {"Retry-After": "1"}
    error = requests.HTTPError("429 Too Many Requests")
    error.response = retry_response

    failing = Mock()
    failing.status_code = 429
    failing.url = "https://example.com/feed"
    failing.text = ""
    failing.headers = {"Retry-After": "1"}
    failing.raise_for_status = Mock(side_effect=error)

    responses = iter([success, failing, failing, failing])
    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: next(responses))

    first = resilient_get(
        "https://example.com/feed",
        headers={"User-Agent": "test"},
        timeout=20,
        logger=Mock(),
        cache_namespace="test_cache",
    )
    second = resilient_get(
        "https://example.com/feed",
        headers={"User-Agent": "test"},
        timeout=20,
        logger=Mock(),
        cache_namespace="test_cache",
    )

    assert first.text == '{"ok": true}'
    assert isinstance(second, CachedHTTPResponse)
    assert second.from_cache is True
    assert second.json()["ok"] is True


def test_resilient_get_uses_recent_cache_immediately_after_connection_error(monkeypatch, tmp_path):
    monkeypatch.setattr("src.fetchers.HTTP_CACHE_DIR", tmp_path / "http_cache")
    sleep_calls: list[int] = []
    monkeypatch.setattr("src.fetchers.time.sleep", lambda seconds: sleep_calls.append(seconds))

    success = Mock()
    success.status_code = 200
    success.url = "https://example.com/feed"
    success.text = '{"ok": true}'
    success.headers = {"content-type": "application/json"}
    success.raise_for_status = Mock()

    error = requests.ConnectionError("DNS failure")
    call_count = {"value": 0}

    def fake_get(*args, **kwargs):
        call_count["value"] += 1
        if call_count["value"] == 1:
            return success
        raise error

    monkeypatch.setattr("src.fetchers.requests.get", fake_get)

    first = resilient_get(
        "https://example.com/feed",
        headers={"User-Agent": "test"},
        timeout=20,
        logger=Mock(),
        cache_namespace="test_cache",
    )
    second = resilient_get(
        "https://example.com/feed",
        headers={"User-Agent": "test"},
        timeout=20,
        logger=Mock(),
        cache_namespace="test_cache",
    )

    assert first.text == '{"ok": true}'
    assert isinstance(second, CachedHTTPResponse)
    assert second.from_cache is True
    assert second.json()["ok"] is True
    assert call_count["value"] == 2
    assert sleep_calls == []


def test_fetch_pubmed_uses_cached_payloads_after_429(monkeypatch, tmp_path):
    monkeypatch.setattr("src.fetchers.HTTP_CACHE_DIR", tmp_path / "http_cache")
    monkeypatch.setattr("src.fetchers.time.sleep", lambda *_args, **_kwargs: None)

    search_response = Mock()
    search_response.status_code = 200
    search_response.url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_response.headers = {"content-type": "application/json"}
    search_response.text = '{"esearchresult": {"idlist": ["42083789"]}}'
    search_response.json = Mock(return_value={"esearchresult": {"idlist": ["42083789"]}})
    search_response.raise_for_status = Mock()

    summary_response = Mock()
    summary_response.status_code = 200
    summary_response.url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    summary_response.headers = {"content-type": "application/json"}
    summary_response.text = """
    {"result": {"42083789": {"title": "A copper uptake ABC transport system is essential for Mycobacterium tuberculosis virulence.", "pubdate": "2026 May 05", "authors": [{"name": "Xu Z"}, {"name": "Tang H"}], "fulljournalname": "Emerging microbes & infections"}}}
    """
    summary_response.json = Mock(
        return_value={
            "result": {
                "42083789": {
                    "title": "A copper uptake ABC transport system is essential for Mycobacterium tuberculosis virulence.",
                    "pubdate": "2026 May 05",
                    "authors": [{"name": "Xu Z"}, {"name": "Tang H"}],
                    "fulljournalname": "Emerging microbes & infections",
                }
            }
        }
    )
    summary_response.raise_for_status = Mock()

    detail_response = Mock()
    detail_response.status_code = 200
    detail_response.url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    detail_response.headers = {"content-type": "application/xml"}
    detail_response.text = """
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>42083789</PMID>
          <Article>
            <Journal>
              <JournalIssue><PubDate><Year>2026</Year><Month>May</Month><Day>05</Day></PubDate></JournalIssue>
              <Title>Emerging microbes &amp; infections</Title>
            </Journal>
            <ArticleTitle>A copper uptake ABC transport system is essential for Mycobacterium tuberculosis virulence.</ArticleTitle>
            <ELocationID EIdType="doi">10.1080/22221751.2026.2668753</ELocationID>
            <Abstract>
              <AbstractText>Deletion of the transporter lowered bacterial burdens in a murine model.</AbstractText>
            </Abstract>
            <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
            <ArticleDate><Year>2026</Year><Month>05</Month><Day>05</Day></ArticleDate>
          </Article>
        </MedlineCitation>
        <PubmedData><PublicationStatus>aheadofprint</PublicationStatus></PubmedData>
      </PubmedArticle>
    </PubmedArticleSet>
    """
    detail_response.raise_for_status = Mock()

    retry_response = Mock()
    retry_response.status_code = 429
    retry_response.headers = {"Retry-After": "1"}
    error = requests.HTTPError("429 Too Many Requests")
    error.response = retry_response

    failing = Mock()
    failing.status_code = 429
    failing.url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    failing.text = ""
    failing.headers = {"Retry-After": "1"}
    failing.raise_for_status = Mock(side_effect=error)

    initial = iter([search_response, summary_response, detail_response])
    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: next(initial))

    source = SourceConfig(
        name="PubMed Infectious Disease Search",
        type="pubmed",
        category="Major epidemiology studies",
        official=True,
        search="tuberculosis",
        max_items=5,
    )
    cached_items = fetch_pubmed(source, logger=Mock(), start_date=date(2026, 5, 4), end_date=date(2026, 5, 5))
    assert len(cached_items) == 1

    failures = iter([failing, failing, failing, failing, failing, failing, failing, failing, failing])
    monkeypatch.setattr("src.fetchers.requests.get", lambda *args, **kwargs: next(failures))

    items = fetch_pubmed(source, logger=Mock(), start_date=date(2026, 5, 4), end_date=date(2026, 5, 5))
    assert len(items) == 1
    assert items[0].doi == "10.1080/22221751.2026.2668753"


def test_fetch_all_sources_uses_source_item_cache_for_refresh_window(monkeypatch, tmp_path):
    monkeypatch.setattr("src.fetchers.SOURCE_ITEM_CACHE_DIR", tmp_path / "source_items")

    source = SourceConfig(
        name="Cached Historical Source",
        type="rss",
        category="Historical",
        url="https://example.com/feed.xml",
        refresh_hours=12,
    )
    first_item = Item(
        title="Cached outbreak item",
        source=source.name,
        url="https://example.com/a",
        category="Historical",
        summary="Cached summary.",
    )

    fetch_calls = {"count": 0}

    def fake_fetch_source(_source, _logger, start_date=None, end_date=None):
        fetch_calls["count"] += 1
        return [first_item]

    monkeypatch.setattr("src.fetchers.fetch_source", fake_fetch_source)

    logger = Mock()
    first_items, first_failures, first_health = fetch_all_sources([source], logger, start_date=date(2026, 5, 4), end_date=date(2026, 5, 5))
    second_items, second_failures, second_health = fetch_all_sources([source], logger, start_date=date(2026, 5, 4), end_date=date(2026, 5, 5))

    assert fetch_calls["count"] == 1
    assert len(first_items) == 1
    assert len(second_items) == 1
    assert first_failures == []
    assert second_failures == []
    assert first_health[0]["mode"] == "live"
    assert second_health[0]["mode"] == "refresh_cache"
    assert second_items[0].metadata["source_freshness"] == "refresh_cache"


def test_fetch_all_sources_uses_source_item_cache_after_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("src.fetchers.SOURCE_ITEM_CACHE_DIR", tmp_path / "source_items")

    source = SourceConfig(
        name="Fallback Cached Source",
        type="rss",
        category="Outbreaks",
        url="https://example.com/feed.xml",
        fallback_cache_hours=48,
    )
    cached_item = Item(
        title="Recovered cached item",
        source=source.name,
        url="https://example.com/cached",
        category="Outbreaks",
        summary="Recovered from cache.",
    )

    call_state = {"count": 0}

    def fake_fetch_source(_source, _logger, start_date=None, end_date=None):
        call_state["count"] += 1
        if call_state["count"] == 1:
            return [cached_item]
        raise RuntimeError("upstream exploded")

    monkeypatch.setattr("src.fetchers.fetch_source", fake_fetch_source)

    logger = Mock()
    initial_items, initial_failures, initial_health = fetch_all_sources([source], logger, start_date=date(2026, 5, 4), end_date=date(2026, 5, 5))
    fallback_items, fallback_failures, fallback_health = fetch_all_sources([source], logger, start_date=date(2026, 5, 4), end_date=date(2026, 5, 5))

    assert len(initial_items) == 1
    assert initial_failures == []
    assert len(fallback_items) == 1
    assert "[cache fallback used]" in fallback_failures[0]["error"]
    assert initial_health[0]["mode"] == "live"
    assert fallback_health[0]["mode"] == "fallback_cache"
    assert fallback_items[0].metadata["source_freshness"] == "fallback_cache"
