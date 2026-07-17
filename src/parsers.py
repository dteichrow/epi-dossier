from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from .utils import absolute_url, normalize_whitespace, parse_datetime


BOILERPLATE_PATTERNS = [
    r"an official website of the united states government",
    r"the \.gov means it'?s official",
    r"federal government websites often end in \.gov or \.mil",
    r"before sharing sensitive information, make sure you'?re on a federal government site",
    r"the site is secure",
    r"the https:// ensures that you are connecting to the official website",
    r"any information you provide is encrypted and transmitted securely",
    r"opens in a new window",
    r"publications and data",
    r"infectious disease topics",
    r"related public health topics",
    r"training and tools",
    r"preparedness, prevention and control tools",
    r"about ecdc",
    r"recalls, market withdrawals and safety alerts",
    r"food safety tips for consumers",
    r"food safety resources for produce shippers and carriers",
]


def extract_html_links(html: str, base_url: str, selector: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    seen_urls: set[str] = set()
    for anchor in soup.select(selector):
        href = anchor.get("href")
        title = normalize_whitespace(anchor.get_text(" ", strip=True))
        if not href or not title:
            continue
        url = absolute_url(base_url, href)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        items.append({"title": title, "url": url})
    return items


def extract_ncdc_news_rows(html: str, base_url: str, max_items: int | None = None) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for article in soup.select("#news article"):
        heading = article.find(["h1", "h2", "h3"])
        anchor = article.parent.find("a", href=True) if article.parent else None
        if heading is None or anchor is None:
            continue
        title = normalize_whitespace(heading.get_text(" ", strip=True))
        url = absolute_url(base_url, str(anchor.get("href", "")))
        if not title or not url or url in seen_urls:
            continue
        seen_urls.add(url)
        date_node = article.find("h4")
        summary = normalize_whitespace(article.get_text(" ", strip=True))
        if date_node:
            date_text = normalize_whitespace(date_node.get_text(" ", strip=True))
            summary = normalize_whitespace(summary.removeprefix(title).removeprefix(date_text))
        items.append(
            {
                "title": title,
                "url": url,
                "published_at": parse_datetime(date_node.get_text(" ", strip=True) if date_node else None),
                "summary": summary,
            }
        )
        if max_items is not None and len(items) >= max_items:
            break
    return items


def extract_page_text(html: str, max_paragraphs: int = 6) -> str:
    soup = BeautifulSoup(html, "html.parser")
    paragraphs: list[str] = []
    for node in soup.find_all(["p", "li"]):
        text = clean_extracted_text(node.get_text(" ", strip=True))
        if len(text) < 40:
            continue
        paragraphs.append(text)
        if len(paragraphs) >= max_paragraphs:
            break
    return "\n".join(paragraphs)


def extract_meta_content(html: str, keys: list[tuple[str, str]]) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for attr_name, attr_value in keys:
        node = soup.find("meta", attrs={attr_name: attr_value})
        if node and node.get("content"):
            return normalize_whitespace(node.get("content", ""))
    return None


def extract_link_href(html: str, rel_value: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    node = soup.find("link", attrs={"rel": lambda rel: rel and rel_value in rel})
    if node and node.get("href"):
        return normalize_whitespace(node.get("href", ""))
    return None


def extract_fda_outbreak_table(html: str, base_url: str, max_items: int | None = None) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    updated_at = extract_meta_content(
        html,
        [
            ("property", "article:modified_time"),
            ("property", "og:updated_time"),
            ("name", "dcterms.modified"),
        ],
    )
    items: list[dict[str, Any]] = []
    seen_rows: set[str] = set()
    for table in soup.find_all("table"):
        header_text = " ".join(normalize_whitespace(th.get_text(" ", strip=True)).lower() for th in table.find_all("th"))
        if "reference" not in header_text or "pathogen" not in header_text:
            continue
        for row in table.select("tbody tr"):
            cells = [clean_extracted_text(td.get_text(" ", strip=True)) for td in row.find_all("td")]
            if len(cells) < 6:
                continue
            date_posted = cells[0]
            reference = cells[1]
            pathogen = cells[2]
            product = cells[3]
            case_count = cells[4]
            investigation_status = cells[5] if len(cells) > 5 else ""
            outbreak_status = cells[6] if len(cells) > 6 else ""
            advisory_url = ""
            for anchor in row.find_all("a", href=True):
                candidate = absolute_url(base_url, anchor["href"])
                if "/outbreak-investigation-" in candidate:
                    advisory_url = candidate
                    break
            row_key = advisory_url or f"{base_url}#reference-{reference}"
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            title = f"FDA outbreak investigation {reference}: {pathogen}"
            if product and product.lower() != "not yet identified":
                title += f" linked to {product}"
            summary_parts = [
                f"FDA lists reference {reference} with date posted {date_posted}.",
                f"Pathogen or cause of illness: {pathogen}.",
                f"Product linked to illnesses: {product}.",
            ]
            if case_count and "see advisory" not in case_count.lower():
                summary_parts.append(f"Reported total case count: {case_count}.")
            if investigation_status:
                summary_parts.append(f"Investigation status: {investigation_status}.")
            if outbreak_status:
                summary_parts.append(f"Outbreak or event status: {outbreak_status}.")
            items.append(
                {
                    "title": title,
                    "url": advisory_url or base_url,
                    "summary": " ".join(summary_parts),
                    "published_at": parse_datetime(updated_at) or parse_datetime(date_posted),
                    "metadata": {
                        "reference_number": reference,
                        "pathogen": pathogen,
                        "product": product,
                        "case_count": case_count,
                        "investigation_status": investigation_status,
                        "outbreak_status": outbreak_status,
                        "page_updated_at": updated_at,
                    },
                }
            )
            if max_items and len(items) >= max_items:
                return items
    return items


FDA_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+[^)]*)?\)")


def extract_fda_outbreak_markdown(markdown: str, base_url: str, max_items: int | None = None) -> list[dict[str, Any]]:
    """Parse the active FDA outbreak table returned by the reader fallback."""
    active_section = markdown.partition("## Active Investigations")[2]
    active_section = active_section.partition("## Closed Investigations")[0]
    if not active_section:
        return []

    items: list[dict[str, Any]] = []
    seen_rows: set[str] = set()
    for line in active_section.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [clean_fda_markdown_cell(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) < 7 or not cells[0] or cells[0].lower().startswith("date") or set(cells[0]) == {"-"}:
            continue

        date_posted, reference, pathogen, product, case_count, investigation_status, outbreak_status = cells[:7]
        if not reference or not pathogen:
            continue
        links = FDA_MARKDOWN_LINK_RE.findall(line)
        advisory_url = next((url for _label, url in links if "/outbreak-investigation-" in url), "")
        row_key = advisory_url or f"{base_url}#reference-{reference}"
        if row_key in seen_rows:
            continue
        seen_rows.add(row_key)

        title = f"FDA outbreak investigation {reference}: {pathogen}"
        if product and product.lower() != "not yet identified":
            title += f" linked to {product}"
        summary_parts = [
            f"FDA lists reference {reference} with date posted {date_posted}.",
            f"Pathogen or cause of illness: {pathogen}.",
            f"Product linked to illnesses: {product}.",
        ]
        if case_count and "see advisory" not in case_count.lower():
            summary_parts.append(f"Reported total case count: {case_count}.")
        if investigation_status:
            summary_parts.append(f"Investigation status: {investigation_status}.")
        if outbreak_status:
            summary_parts.append(f"Outbreak or event status: {outbreak_status}.")
        items.append(
            {
                "title": title,
                "url": advisory_url or base_url,
                "summary": " ".join(summary_parts),
                "published_at": parse_datetime(date_posted),
                "metadata": {
                    "reference_number": reference,
                    "pathogen": pathogen,
                    "product": product,
                    "case_count": case_count,
                    "investigation_status": investigation_status,
                    "outbreak_status": outbreak_status,
                    "collection_mode": "reader_fallback",
                },
            }
        )
        if max_items and len(items) >= max_items:
            break
    return items


def clean_fda_markdown_cell(value: str) -> str:
    value = FDA_MARKDOWN_LINK_RE.sub(lambda match: match.group(1), value)
    value = re.sub(r"[*_`]", "", value)
    return normalize_whitespace(value)


def parse_pubmed_details_xml(xml_text: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return records
    for article in root.findall(".//PubmedArticle"):
        pmid = text_at(article, ".//PMID")
        if not pmid:
            continue
        article_node = article.find(".//Article")
        if article_node is None:
            continue
        abstract_parts = [
            clean_extracted_text(" ".join(node.itertext()).strip())
            for node in article_node.findall(".//AbstractText")
        ]
        abstract = " ".join(part for part in abstract_parts if part)
        doi = None
        for node in article.findall(".//ArticleId"):
            if node.attrib.get("IdType") == "doi":
                doi = normalize_whitespace("".join(node.itertext()).strip())
                break
        if not doi:
            for node in article_node.findall(".//ELocationID"):
                if node.attrib.get("EIdType") == "doi":
                    doi = normalize_whitespace("".join(node.itertext()).strip())
                    break
        publication_types = [
            clean_extracted_text(" ".join(node.itertext()).strip())
            for node in article_node.findall(".//PublicationType")
            if clean_extracted_text(" ".join(node.itertext()).strip())
        ]
        comment_source = ""
        comment_node = article.find(".//CommentsCorrections/RefSource")
        if comment_node is not None and "".join(comment_node.itertext()).strip():
            comment_source = clean_comment_source(" ".join(comment_node.itertext()).strip())
        fallback_parts: list[str] = []
        if publication_types:
            fallback_parts.append(f"Publication type: {', '.join(publication_types[:2])}.")
        if comment_source:
            fallback_parts.append(f"Linked record note: {comment_source}")
        published_at = parse_pubmed_article_date(article)
        records[pmid] = {
            "abstract": abstract,
            "doi": doi,
            "journal": clean_extracted_text(text_at(article_node, ".//Journal/Title")),
            "published_at": published_at,
            "publication_types": publication_types,
            "publication_status": clean_extracted_text(text_at(article, ".//PublicationStatus")),
            "fallback_summary": " ".join(fallback_parts).strip(),
        }
    return records


def parse_pubmed_article_date(article_node) -> Any:
    article_date = article_node.find(".//ArticleDate")
    if article_date is not None:
        parsed = build_pubmed_date(article_date)
        if parsed:
            return parsed
    pub_date = article_node.find(".//PubDate")
    if pub_date is not None:
        return build_pubmed_date(pub_date)
    return None


def build_pubmed_date(node) -> Any:
    year = text_at(node, "./Year")
    month = text_at(node, "./Month")
    day = text_at(node, "./Day")
    parts = [part for part in (year, month, day) if part]
    if not parts:
        return None
    return parse_datetime(" ".join(parts))


def text_at(node, path: str) -> str:
    child = node.find(path)
    if child is None:
        return ""
    return normalize_whitespace(" ".join(child.itertext()).strip())


def clean_comment_source(text: str) -> str:
    cleaned = clean_extracted_text(text)
    cleaned = re.sub(r"\bdoi:\s*\S+\.?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bPMID\s*\d+\.?", "", cleaned, flags=re.IGNORECASE)
    return normalize_whitespace(cleaned.strip(" .;"))


def clean_extracted_text(text: str) -> str:
    cleaned = normalize_whitespace(text)
    lowered = cleaned.lower()
    if is_boilerplate(lowered):
        return ""
    for pattern in BOILERPLATE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*[-|]\s*(reuters|associated press|ap|yahoo|msn|aol\.com|abc news|nbc news|fox news|sky news|newsnation|ndtv|wfla|kcra|wdiv local 4|firstcoastnews\.com|lookout santa cruz|sfgate|the salt lake tribune)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = normalize_whitespace(cleaned)
    return cleaned


def is_boilerplate(text: str) -> bool:
    if not text:
        return True
    boilerplate_hits = sum(1 for pattern in BOILERPLATE_PATTERNS if re.search(pattern, text, flags=re.IGNORECASE))
    if boilerplate_hits >= 2:
        return True
    if len(set(text.split())) < 8 and len(text.split()) > 12:
        return True
    return False
