from __future__ import annotations

import html
import logging
import re
import hashlib
import json
from functools import lru_cache
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlparse, urlunparse

import yaml
from dateutil import parser as date_parser


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
BRIEFINGS_DIR = ROOT_DIR / "Daily Dossiers"
LEGACY_BRIEFINGS_DIR = ROOT_DIR / "briefings"
APP_EXPORTS_DIR = ROOT_DIR / "app_exports"
SQLITE_PATH = DATA_DIR / "dossier.sqlite"
LOG_PATH = LOG_DIR / "dossier.log"

REGION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Global / Maritime": ("cruise ship", "aboard", "maritime", "at sea", "docking", "port"),
    "Africa": (
        "africa", "uganda", "kenya", "tanzania", "ethiopia", "nigeria", "ghana", "liberia", "sierra leone",
        "congo", "drc", "democratic republic of the congo", "sudan", "south sudan", "somalia", "malawi",
        "zambia", "zimbabwe", "mozambique", "botswana", "namibia", "rwanda", "burundi", "cameroon",
        "chad", "niger", "mali", "senegal", "guinea", "angola", "madagascar", "lesotho", "eswatini",
    ),
    "Latin America and Caribbean": (
        "latin america", "caribbean", "brazil", "argentina", "chile", "peru", "bolivia", "paraguay", "uruguay",
        "colombia", "ecuador", "venezuela", "mexico", "guatemala", "honduras", "el salvador", "nicaragua",
        "costa rica", "panama", "haiti", "dominican republic", "jamaica", "cuba", "puerto rico",
    ),
    "South Asia": (
        "south asia", "india", "pakistan", "bangladesh", "nepal", "bhutan", "sri lanka", "afghanistan", "maldives",
    ),
    "Southeast Asia": (
        "southeast asia", "indonesia", "philippines", "vietnam", "thailand", "cambodia", "laos", "myanmar",
        "malaysia", "singapore", "timor-leste", "brunei",
    ),
    "East Asia": (
        "east asia", "china", "japan", "south korea", "north korea", "taiwan", "hong kong", "mongolia",
    ),
    "Middle East": (
        "middle east", "yemen", "saudi arabia", "oman", "uae", "united arab emirates", "qatar", "bahrain",
        "kuwait", "iraq", "iran", "syria", "jordan", "lebanon", "israel", "palestinian", "gaza", "west bank",
    ),
    "Europe": (
        "europe", "eu", "uk", "united kingdom", "england", "scotland", "wales", "ireland", "france", "germany",
        "spain", "portugal", "italy", "greece", "poland", "romania", "bulgaria", "ukraine", "switzerland",
        "netherlands", "belgium", "slovakia", "czechia", "sweden", "norway", "finland", "denmark",
    ),
    "North America": (
        "north america", "united states", "u.s.", "usa", "canada", "texas", "california", "florida", "new york",
        "washington", "oregon", "alaska", "arizona", "county", "cdc", "mmwr",
    ),
    "Oceania": (
        "oceania", "australia", "new zealand", "papua new guinea", "fiji", "samoa", "tonga",
    ),
}

LOCAL_SIGNAL_TERMS = (
    "rural", "village", "villages", "district", "province", "county", "governorate", "settlement",
    "hamlet", "remote", "pastoralist", "camp", "tribal", "municipality", "ward",
)


@dataclass
class SourceConfig:
    name: str
    type: str
    category: str
    official: bool = False
    outbreak_signal: bool = False
    occupational_relevance: bool = False
    historical_relevance: bool = False
    required: bool = True
    url: str | None = None
    search: str | None = None
    item_selector: str | None = None
    terms_hint: list[str] = field(default_factory=list)
    max_items: int | None = None
    refresh_hours: int | None = None
    fallback_cache_hours: int | None = 48
    timeout_seconds: int | None = None
    max_attempts: int | None = None
    verify_ssl: bool = True


@dataclass
class EmailConfig:
    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    use_ssl: bool = True
    username: str | None = None
    password_env: str = "EPI_DOSSIER_EMAIL_APP_PASSWORD"
    from_email: str | None = None
    to_email: str | None = None
    subject_prefix: str = "Daily Epidemiology Dossier"


@dataclass
class PublisherProfile:
    key: str
    name: str
    domains: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    tier: str = "general"
    access: str = "open"


@dataclass
class Item:
    title: str
    source: str
    url: str
    category: str
    publisher: str | None = None
    published_at: datetime | None = None
    summary: str = ""
    why_it_matters: str = ""
    caveats: str = ""
    relevance_score: int = 1
    doi: str | None = None
    journal: str | None = None
    abstract_url: str | None = None
    source_type: str | None = None
    official: bool = False
    extracted_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.url = normalize_public_url(self.url)
        if self.abstract_url:
            self.abstract_url = normalize_public_url(self.abstract_url)
        for key in ("raw_url", "aggregator_url", "resolved_url"):
            value = self.metadata.get(key)
            if isinstance(value, str):
                self.metadata[key] = normalize_public_url(value)

    @property
    def canonical_url(self) -> str:
        return canonicalize_url(self.url)

    @property
    def display_source(self) -> str:
        return normalize_whitespace(self.publisher or self.source)

    @property
    def publisher_profile(self) -> PublisherProfile | None:
        return match_publisher(self.publisher, self.url)

    @property
    def publisher_name(self) -> str:
        profile = self.publisher_profile
        return profile.name if profile else self.display_source

    @property
    def publisher_tier(self) -> str:
        profile = self.publisher_profile
        return profile.tier if profile else ("official" if self.official else "general")

    @property
    def publisher_access(self) -> str:
        profile = self.publisher_profile
        return profile.access if profile else "unknown"

    @property
    def aggregator_source(self) -> str | None:
        value = self.metadata.get("aggregator_source")
        return normalize_whitespace(value) if value else None

    @property
    def raw_url(self) -> str:
        return str(self.metadata.get("raw_url") or self.metadata.get("aggregator_url") or self.url)

    @property
    def resolved_url(self) -> str | None:
        value = self.metadata.get("resolved_url")
        if value:
            return str(value)
        if self.raw_url != self.url:
            return self.url
        return None

    @property
    def preferred_url(self) -> str:
        return self.resolved_url or self.url

    @property
    def link_quality(self) -> str:
        summary_text = self.summary.lower()
        if summary_text.startswith("limited detail") or summary_text.startswith("limited usable detail"):
            return "metadata_only"
        if self.aggregator_source and self.resolved_url:
            return self.preferred_url_kind
        if self.aggregator_source:
            return "wrapper_only"
        return "direct_article"

    @property
    def preferred_url_kind(self) -> str:
        if self.summary.lower().startswith("limited detail") or self.summary.lower().startswith("limited usable detail"):
            return "metadata_only"
        if not self.aggregator_source:
            return "direct_article"
        parsed = urlparse(self.preferred_url)
        path = parsed.path.lower()
        if any(marker in path for marker in ("/video", "/videos", "/watch", "/live", "/topic", "/topics")):
            return "resolved_nonarticle"
        if any(marker in path for marker in ("/article", "/articles", "/story", "/stories", "/news", "/world", "/health")) or re.search(r"/\d{4}/\d{2}/", path):
            return "resolved_article"
        return "resolved_article" if self.resolved_url else "wrapper_only"

    @property
    def source_confidence(self) -> str:
        if self.official:
            return "official_agency"
        if self.link_quality == "metadata_only":
            return "metadata_only_signal"
        if self.link_quality == "wrapper_only":
            return "aggregator_only"
        return {
            "wire": "wire",
            "major_newsroom": "major_newsroom",
            "specialist_health": "specialist_health",
            "general": "general_outlet",
        }.get(self.publisher_tier, "general_outlet")

    @property
    def evidence_type(self) -> str:
        return {
            "pubmed": "journal_article",
            "medrxiv": "preprint",
            "biorxiv": "preprint",
            "rss": "news_report",
            "html_list": "official_update" if self.official else "news_report",
        }.get(self.source_type or "", "news_report")


@dataclass
class OutbreakEventReference:
    label: str
    period: str
    location: str
    summary: str
    source_name: str
    source_url: str
    as_of: str

    def __post_init__(self) -> None:
        self.source_url = normalize_public_url(self.source_url)


@dataclass
class ReferenceLink:
    label: str
    url: str

    def __post_init__(self) -> None:
        self.url = normalize_public_url(self.url)


@dataclass
class DiseaseReference:
    name: str
    pathogen: str
    transmission: str
    categories: list[str]
    latest_outbreak: OutbreakEventReference
    aliases: list[str] = field(default_factory=list)
    notable_outbreaks: list[str] = field(default_factory=list)
    surveillance_note: str = ""
    field_guide_links: list[ReferenceLink] = field(default_factory=list)
    reservoir_or_vector: str = ""
    incubation: str = ""
    symptoms: list[str] = field(default_factory=list)
    severity: str = ""
    diagnostics: str = ""
    treatment: str = ""
    prevention: str = ""
    outbreak_settings: list[str] = field(default_factory=list)
    vaccine_status: str = ""
    research_caveats: str = ""
    why_reporters_care: str = ""
    what_reporters_get_wrong: str = ""
    metrics_that_matter: list[str] = field(default_factory=list)


@dataclass
class PathogenAtlasRoute:
    route_id: str
    from_label: str
    to_label: str
    from_coordinates: list[float]
    to_coordinates: list[float]
    date_or_era: str
    route_type: str
    confidence: str
    narrative: str
    citation_ids: list[str] = field(default_factory=list)


@dataclass
class PathogenAtlasEntry:
    slug: str
    name: str
    subtitle: str
    status: str
    pathogen_type: str
    summary: str
    why_it_matters: str
    atlas_scope: str
    origin_claim: dict[str, Any]
    spread_routes: list[PathogenAtlasRoute] = field(default_factory=list)
    modern_echoes: list[str] = field(default_factory=list)
    framing_traps: list[str] = field(default_factory=list)
    linked_reference_slug: str = ""
    linked_story_ids: list[str] = field(default_factory=list)
    linked_blog_posts: list[dict[str, str]] = field(default_factory=list)
    citations: list[dict[str, str]] = field(default_factory=list)
    visual_asset_id: str = ""


@dataclass
class EditorialConfig:
    pinned_story_topics: list[str] = field(default_factory=list)
    forced_story_retention_days: dict[str, int] = field(default_factory=dict)
    suppressed_story_ids: list[str] = field(default_factory=list)
    story_aliases: dict[str, str] = field(default_factory=dict)
    promoted_publishers: list[str] = field(default_factory=list)
    spotlight_reference_names: list[str] = field(default_factory=list)


@dataclass
class EditionConfig:
    key: str
    label: str
    page: str
    description: str = ""
    regions: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    source_confidence: list[str] = field(default_factory=list)
    evidence_types: list[str] = field(default_factory=list)
    story_statuses: list[str] = field(default_factory=list)
    publisher_families: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    include_terms: list[str] = field(default_factory=list)
    exclude_terms: list[str] = field(default_factory=list)
    official_only: bool = False
    include_story_items: bool = True
    include_story_cards: bool = True
    max_items: int = 12
    max_stories: int = 6
    rank_bias: str = "recent"


@dataclass(frozen=True)
class ArchiveEntry:
    target_date: date
    html_path: Path
    markdown_path: Path


def ensure_directories() -> None:
    for path in (CONFIG_DIR, DATA_DIR, LOG_DIR, BRIEFINGS_DIR, LEGACY_BRIEFINGS_DIR, APP_EXPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def setup_logging() -> logging.Logger:
    ensure_directories()
    logger = logging.getLogger("epi_dossier")
    logger.setLevel(logging.INFO)
    if not any(isinstance(handler, logging.FileHandler) and handler.baseFilename == str(LOG_PATH) for handler in logger.handlers):
        file_handler = logging.FileHandler(LOG_PATH)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def load_sources() -> list[SourceConfig]:
    raw = load_yaml(CONFIG_DIR / "sources.yml").get("sources", [])
    return [SourceConfig(**entry) for entry in raw]


def load_search_terms() -> list[str]:
    raw = load_yaml(CONFIG_DIR / "search_terms.yml")
    return list(raw.get("priority_terms", []))


def load_outbreak_reference() -> list[DiseaseReference]:
    raw = load_yaml(CONFIG_DIR / "outbreak_reference.yml").get("diseases", [])
    entries: list[DiseaseReference] = []
    for entry in raw:
        latest = OutbreakEventReference(**entry["latest_outbreak"])
        field_guide_links = [ReferenceLink(**link) for link in entry.get("field_guide_links", [])]
        entries.append(
            DiseaseReference(
                name=entry["name"],
                pathogen=entry["pathogen"],
                transmission=entry["transmission"],
                categories=list(entry.get("categories", [])),
                latest_outbreak=latest,
                aliases=list(entry.get("aliases", [])),
                notable_outbreaks=list(entry.get("notable_outbreaks", [])),
                surveillance_note=entry.get("surveillance_note", ""),
                field_guide_links=field_guide_links,
                reservoir_or_vector=entry.get("reservoir_or_vector", ""),
                incubation=entry.get("incubation", ""),
                symptoms=list(entry.get("symptoms", [])),
                severity=entry.get("severity", ""),
                diagnostics=entry.get("diagnostics", ""),
                treatment=entry.get("treatment", ""),
                prevention=entry.get("prevention", ""),
                outbreak_settings=list(entry.get("outbreak_settings", [])),
                vaccine_status=entry.get("vaccine_status", ""),
                research_caveats=entry.get("research_caveats", ""),
                why_reporters_care=entry.get("why_reporters_care", ""),
                what_reporters_get_wrong=entry.get("what_reporters_get_wrong", ""),
                metrics_that_matter=list(entry.get("metrics_that_matter", [])),
            )
        )
    return entries


def _normalize_coordinates(value: Any, *, field_name: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{field_name} must be a two-item coordinate list")
    return [float(value[0]), float(value[1])]


def _normalize_atlas_entry(raw: dict[str, Any], *, field_prefix: str) -> dict[str, Any]:
    slug = slugify(str(raw["slug"]))
    origin_claim = dict(raw["origin_claim"])
    origin_claim["coordinates"] = _normalize_coordinates(
        origin_claim.get("coordinates"),
        field_name=f"{field_prefix}.{slug}.origin_claim.coordinates",
    )
    routes: list[dict[str, Any]] = []
    for route in raw.get("spread_routes", []):
        routes.append(
            {
                "route_id": str(route["route_id"]),
                "from_label": str(route["from_label"]),
                "to_label": str(route["to_label"]),
                "from_coordinates": _normalize_coordinates(
                    route.get("from_coordinates"),
                    field_name=f"{field_prefix}.{slug}.{route['route_id']}.from_coordinates",
                ),
                "to_coordinates": _normalize_coordinates(
                    route.get("to_coordinates"),
                    field_name=f"{field_prefix}.{slug}.{route['route_id']}.to_coordinates",
                ),
                "date_or_era": str(route["date_or_era"]),
                "route_type": str(route["route_type"]),
                "confidence": str(route["confidence"]),
                "narrative": str(route["narrative"]),
                "citation_ids": [str(value) for value in route.get("citation_ids", [])],
            }
        )
    citations = [dict(citation) for citation in raw.get("citations", [])]
    if not citations:
        raise ValueError(f"{field_prefix}.{slug} must define at least one citation")
    entry = {
        "slug": slug,
        "name": str(raw["name"]),
        "subtitle": str(raw.get("subtitle", "")),
        "status": str(raw.get("status", "mixed")),
        "pathogen_type": str(raw.get("pathogen_type", "")),
        "summary": str(raw.get("summary", "")),
        "why_it_matters": str(raw.get("why_it_matters", "")),
        "atlas_scope": str(raw.get("atlas_scope", "")),
        "origin_claim": origin_claim,
        "spread_routes": routes,
        "modern_echoes": [str(value) for value in raw.get("modern_echoes", [])],
        "framing_traps": [str(value) for value in raw.get("framing_traps", [])],
        "linked_reference_slug": slugify(str(raw.get("linked_reference_slug", ""))),
        "linked_story_ids": [str(value) for value in raw.get("linked_story_ids", [])],
        "linked_blog_posts": [dict(post) for post in raw.get("linked_blog_posts", [])],
        "citations": citations,
        "visual_asset_id": str(raw.get("visual_asset_id", "")),
    }
    variants: list[dict[str, Any]] = []
    for raw_variant in raw.get("variants", []):
        variant_payload = {
            "pathogen_type": entry["pathogen_type"],
            "atlas_scope": entry["atlas_scope"],
            "linked_reference_slug": entry["linked_reference_slug"],
            "linked_story_ids": list(entry["linked_story_ids"]),
            "linked_blog_posts": [dict(post) for post in entry["linked_blog_posts"]],
            "visual_asset_id": entry["visual_asset_id"],
            **dict(raw_variant),
        }
        variants.append(
            _normalize_atlas_entry(
                variant_payload,
                field_prefix=f"{field_prefix}.{slug}.variants",
            )
        )
    if variants:
        variant_slugs = {variant["slug"] for variant in variants}
        default_variant_slug = slugify(str(raw.get("default_variant_slug", variants[0]["slug"])))
        if default_variant_slug not in variant_slugs:
            raise ValueError(f"{field_prefix}.{slug}.default_variant_slug must match a variant slug")
        entry["default_variant_slug"] = default_variant_slug
        entry["variants"] = variants
    else:
        entry["default_variant_slug"] = ""
        entry["variants"] = []
    return entry


@lru_cache(maxsize=1)
def load_pathogen_atlas() -> tuple[dict[str, Any], ...]:
    path = CONFIG_DIR / "pathogen_atlas.yml"
    if not path.exists():
        return tuple()
    raw_entries = load_yaml(path).get("pathogens", [])
    entries = [_normalize_atlas_entry(dict(raw), field_prefix="pathogens") for raw in raw_entries]
    return tuple(entries)


@lru_cache(maxsize=1)
def load_atlas_visual_manifest() -> tuple[dict[str, Any], ...]:
    path = ROOT_DIR / "graphics" / "atlas" / "manifest.yml"
    if not path.exists():
        return tuple()
    raw = load_yaml(path).get("assets", [])
    return tuple(dict(entry) for entry in raw)


def load_editorial_config() -> EditorialConfig:
    path = CONFIG_DIR / "editorial.yml"
    if not path.exists():
        return EditorialConfig()
    raw = load_yaml(path).get("editorial", {})
    return EditorialConfig(
        pinned_story_topics=list(raw.get("pinned_story_topics", [])),
        forced_story_retention_days=dict(raw.get("forced_story_retention_days", {})),
        suppressed_story_ids=list(raw.get("suppressed_story_ids", [])),
        story_aliases=dict(raw.get("story_aliases", {})),
        promoted_publishers=list(raw.get("promoted_publishers", [])),
        spotlight_reference_names=list(raw.get("spotlight_reference_names", [])),
    )


def load_editions_config() -> list[EditionConfig]:
    path = CONFIG_DIR / "editions.yml"
    if not path.exists():
        return []
    raw = load_yaml(path).get("editions", [])
    if isinstance(raw, dict):
        entries = [{"key": key, **value} for key, value in raw.items()]
    else:
        entries = list(raw)
    return [
        EditionConfig(
            key=entry["key"],
            label=entry["label"],
            page=entry["page"],
            description=entry.get("description", ""),
            regions=list(entry.get("regions", [])),
            countries=list(entry.get("countries", [])),
            source_confidence=list(entry.get("source_confidence", [])),
            evidence_types=list(entry.get("evidence_types", [])),
            story_statuses=list(entry.get("story_statuses", [])),
            publisher_families=list(entry.get("publisher_families", [])),
            sources=list(entry.get("sources", [])),
            categories=list(entry.get("categories", [])),
            include_terms=list(entry.get("include_terms", [])),
            exclude_terms=list(entry.get("exclude_terms", [])),
            official_only=bool(entry.get("official_only", False)),
            include_story_items=bool(entry.get("include_story_items", True)),
            include_story_cards=bool(entry.get("include_story_cards", True)),
            max_items=int(entry.get("max_items", 12)),
            max_stories=int(entry.get("max_stories", 6)),
            rank_bias=str(entry.get("rank_bias", "recent")),
        )
        for entry in entries
    ]


def load_email_config() -> EmailConfig:
    path = CONFIG_DIR / "email.yml"
    if not path.exists():
        return EmailConfig()
    raw = load_yaml(path).get("email", {})
    return EmailConfig(**raw)


@lru_cache(maxsize=1)
def load_publishers() -> tuple[PublisherProfile, ...]:
    raw = load_yaml(CONFIG_DIR / "publishers.yml").get("publishers", [])
    return tuple(PublisherProfile(**entry) for entry in raw)


def resolve_email_password(config: EmailConfig) -> str | None:
    if not config.password_env:
        return None
    return os.environ.get(config.password_env)


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    try:
        return date_parser.parse(str(value))
    except (ValueError, TypeError, OverflowError):
        return None


def canonicalize_url(url: str) -> str:
    parsed = urlparse(normalize_public_url(url))
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if not key.lower().startswith("utm_")]
    cleaned = parsed._replace(
        scheme=parsed.scheme.lower() or "https",
        netloc=netloc,
        fragment="",
        query="&".join(f"{key}={value}" for key, value in query),
    )
    normalized = urlunparse(cleaned)
    return normalized[:-1] if normalized.endswith("/") else normalized


def normalize_public_url(url: str) -> str:
    return (
        str(url or "")
        .strip()
        .replace("\\=", "=")
        .replace("\\&", "&")
        .replace("\\?", "?")
    )


def absolute_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


REFERENCE_SIGNAL_STOP_TERMS = {
    "bacteria",
    "bacterium",
    "disease",
    "diseases",
    "fever",
    "haemorrhagic fever",
    "hemorrhagic fever",
    "infection",
    "infections",
    "parasite",
    "species",
    "syndrome",
    "viral haemorrhagic fever",
    "viral hemorrhagic fever",
    "virus",
    "viruses",
}


def normalize_signal_text(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", (text or "").lower())
    return normalize_whitespace(cleaned)


def signal_term_matches(haystack: str, term: str) -> bool:
    if not haystack or not term:
        return False
    return re.search(r"\b" + re.escape(term) + r"\b", haystack) is not None


def reference_signal_term_is_useful(term: str) -> bool:
    normalized = normalize_signal_text(term)
    if len(normalized) < 3:
        return False
    tokens = normalized.split()
    if not tokens:
        return False
    if normalized in REFERENCE_SIGNAL_STOP_TERMS:
        return False
    if len(tokens) == 1 and tokens[0] in REFERENCE_SIGNAL_STOP_TERMS:
        return False
    return True


def collect_reference_signal_terms(entry: dict[str, Any]) -> tuple[str, ...]:
    raw_terms = [
        entry.get("name", ""),
        entry.get("pathogen", ""),
        *entry.get("aliases", []),
    ]
    terms: set[str] = set()
    for raw_value in raw_terms:
        value = str(raw_value or "")
        normalized = normalize_signal_text(value)
        if reference_signal_term_is_useful(normalized):
            terms.add(normalized)
        head = normalize_signal_text(value.split(",", 1)[0])
        if reference_signal_term_is_useful(head):
            terms.add(head)
        for chunk in re.findall(r"\(([^)]+)\)", value):
            parenthetical = normalize_signal_text(chunk)
            if reference_signal_term_is_useful(parenthetical):
                terms.add(parenthetical)
    return tuple(sorted(terms, key=lambda term: (len(term.split()), len(term)), reverse=True))


@lru_cache(maxsize=1)
def load_disease_reference_topic_terms() -> tuple[tuple[str, tuple[str, ...]], ...]:
    raw_entries = load_yaml(CONFIG_DIR / "outbreak_reference.yml").get("diseases", [])
    topic_terms: list[tuple[str, tuple[str, ...]]] = []
    for entry in raw_entries:
        name = normalize_whitespace(str(entry.get("name", "")))
        terms = collect_reference_signal_terms(dict(entry))
        if name and terms:
            topic_terms.append((name, terms))
    return tuple(topic_terms)


@lru_cache(maxsize=1)
def load_disease_signal_terms() -> tuple[str, ...]:
    terms = {
        term
        for _, reference_terms in load_disease_reference_topic_terms()
        for term in reference_terms
    }
    return tuple(sorted(terms, key=lambda term: (len(term.split()), len(term)), reverse=True))


def matched_disease_reference_names(text: str) -> list[str]:
    haystack = normalize_signal_text(text)
    if not haystack:
        return []
    matches: list[str] = []
    for name, terms in load_disease_reference_topic_terms():
        if any(signal_term_matches(haystack, term) for term in terms):
            matches.append(name)
    return matches


def has_disease_reference_signal(text: str) -> bool:
    haystack = normalize_signal_text(text)
    if not haystack:
        return False
    return any(signal_term_matches(haystack, term) for term in load_disease_signal_terms())


def normalize_source_name(text: str | None) -> str:
    if not text:
        return ""
    normalized = normalize_whitespace(text)
    normalized = re.sub(r"\s+\|.*$", "", normalized).strip()
    return normalized


def infer_publisher_from_url(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for profile in load_publishers():
        if any(host == domain or host.endswith(f".{domain}") for domain in profile.domains):
            return profile.name
    return None


def match_publisher(name: str | None, url: str | None = None) -> PublisherProfile | None:
    normalized_name = normalize_source_name(name).lower()
    host = ""
    if url:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
    for profile in load_publishers():
        aliases = [profile.name, *profile.aliases]
        if normalized_name and any(normalized_name == normalize_source_name(alias).lower() for alias in aliases):
            return profile
        if host and any(host == domain or host.endswith(f".{domain}") for domain in profile.domains):
            return profile
    return None


def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize_whitespace(text)


def clean_headline(text: str) -> str:
    cleaned = strip_html(text)
    if " - " in cleaned:
        head, tail = cleaned.rsplit(" - ", 1)
        if 1 <= len(tail.split()) <= 5:
            cleaned = head
    return normalize_whitespace(cleaned.rstrip(" -|:"))


def safe_filename(target_date: date) -> Path:
    path = BRIEFINGS_DIR / archive_relpath(target_date, suffix=".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def safe_html_filename(target_date: date) -> Path:
    path = BRIEFINGS_DIR / archive_relpath(target_date, suffix=".html")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def legacy_briefing_filename(target_date: date) -> Path:
    LEGACY_BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    return LEGACY_BRIEFINGS_DIR / f"{target_date.isoformat()}_epi_dossier.md"


def legacy_briefing_html_filename(target_date: date) -> Path:
    LEGACY_BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)
    return LEGACY_BRIEFINGS_DIR / f"{target_date.isoformat()}_epi_dossier.html"


def latest_filename() -> Path:
    return BRIEFINGS_DIR / "latest.md"


def latest_html_filename() -> Path:
    return BRIEFINGS_DIR / "latest.html"


def site_index_filename() -> Path:
    return BRIEFINGS_DIR / "index.html"


def stories_dir() -> Path:
    path = BRIEFINGS_DIR / "stories"
    path.mkdir(parents=True, exist_ok=True)
    return path


def reference_dir() -> Path:
    path = BRIEFINGS_DIR / "reference"
    path.mkdir(parents=True, exist_ok=True)
    return path


def slugify(value: str) -> str:
    normalized = normalize_whitespace(value).lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    return normalized or "untitled"


def story_relpath(story_id: str, topic_name: str) -> Path:
    return Path("stories") / f"{story_id}-{slugify(topic_name)}.html"


def reference_relpath(name: str) -> Path:
    return Path("reference") / f"{slugify(name)}.html"


def archive_relpath(target_date: date, *, suffix: str = ".html") -> Path:
    return Path(f"{target_date:%Y}") / f"{target_date:%m}" / f"{target_date.isoformat()}{suffix}"


def story_filename(story_id: str, topic_name: str) -> Path:
    return BRIEFINGS_DIR / story_relpath(story_id, topic_name)


def reference_filename(name: str) -> Path:
    return BRIEFINGS_DIR / reference_relpath(name)


def docs_dir(deploy_dir: str | Path = "docs") -> Path:
    path = ROOT_DIR / Path(deploy_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def docs_index_filename(deploy_dir: str | Path = "docs") -> Path:
    return docs_dir(deploy_dir) / "index.html"


def docs_desk_filename(slug: str, deploy_dir: str | Path = "docs") -> Path:
    return docs_dir(deploy_dir) / f"{slug}.html"


def docs_archive_index_filename(deploy_dir: str | Path = "docs") -> Path:
    path = docs_dir(deploy_dir) / "archive"
    path.mkdir(parents=True, exist_ok=True)
    return path / "index.html"


def docs_story_filename(story_id: str, topic_name: str, deploy_dir: str | Path = "docs") -> Path:
    path = docs_dir(deploy_dir) / story_relpath(story_id, topic_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def docs_reference_filename(name: str, deploy_dir: str | Path = "docs") -> Path:
    path = docs_dir(deploy_dir) / reference_relpath(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def docs_archive_filename(target_date: date, deploy_dir: str | Path = "docs", *, suffix: str = ".html") -> Path:
    path = docs_dir(deploy_dir) / archive_relpath(target_date, suffix=suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def relative_site_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def relative_href(from_path: Path, to_path: Path) -> str:
    return os.path.relpath(to_path, start=from_path.parent).replace(os.sep, "/")


def app_exports_dir() -> Path:
    APP_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return APP_EXPORTS_DIR


def list_briefing_archives(include_date: date | None = None) -> list[ArchiveEntry]:
    entries: dict[date, ArchiveEntry] = {}
    for path in BRIEFINGS_DIR.glob("[0-9][0-9][0-9][0-9]/*/*.html"):
        try:
            target_date = date.fromisoformat(path.stem)
        except ValueError:
            continue
        entries[target_date] = ArchiveEntry(
            target_date=target_date,
            html_path=path,
            markdown_path=path.with_suffix(".md"),
        )
    if include_date and include_date not in entries:
        entries[include_date] = ArchiveEntry(
            target_date=include_date,
            html_path=safe_html_filename(include_date),
            markdown_path=safe_filename(include_date),
        )
    return sorted(entries.values(), key=lambda entry: entry.target_date, reverse=True)


def infer_region(item: Item) -> str:
    text = " ".join(
        [
            item.title.lower(),
            item.summary.lower(),
            item.category.lower(),
            item.source.lower(),
            (item.publisher or "").lower(),
            item.url.lower(),
        ]
    )
    for region, keywords in REGION_KEYWORDS.items():
        if any(text_contains_keyword(text, keyword) for keyword in keywords):
            return region
    return "Cross-region / unassigned"


def has_local_signal(item: Item) -> bool:
    text = " ".join([item.title.lower(), item.summary.lower(), item.category.lower(), item.url.lower()])
    return any(text_contains_keyword(text, term) for term in LOCAL_SIGNAL_TERMS)


def text_contains_keyword(text: str, keyword: str) -> bool:
    return re.search(r"\b" + re.escape(keyword.lower()) + r"\b", text) is not None


def format_timestamp(value: datetime | None) -> str:
    if not value:
        return "Unknown"
    return value.isoformat(timespec="minutes")


def sortable_datetime(value: datetime | None) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def daterange_backwards(end_date: date, days: int) -> list[date]:
    return [end_date - timedelta(days=offset) for offset in range(days)]


def stable_id(prefix: str, *parts: str) -> str:
    payload = "||".join(normalize_whitespace(part) for part in parts if part is not None)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)
