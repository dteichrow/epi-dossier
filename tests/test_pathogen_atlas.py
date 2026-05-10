from __future__ import annotations

from src.app_exports import build_atlas_records
from src.utils import load_pathogen_atlas


def test_load_pathogen_atlas_exposes_family_variants() -> None:
    load_pathogen_atlas.cache_clear()
    atlas = load_pathogen_atlas()
    hantavirus = next(entry for entry in atlas if entry["slug"] == "hantavirus")

    assert hantavirus["name"] == "Hantaviruses"
    assert hantavirus["default_variant_slug"] == "hantaan-virus"
    assert [variant["slug"] for variant in hantavirus["variants"]] == [
        "hantaan-virus",
        "sin-nombre-virus",
        "andes-virus",
    ]


def test_build_atlas_records_preserves_variant_specific_urls_and_family_reference() -> None:
    atlas_entries = (
        {
            "slug": "hantavirus",
            "name": "Hantaviruses",
            "subtitle": "Family entry",
            "status": "mixed",
            "pathogen_type": "Virus",
            "summary": "Family summary",
            "why_it_matters": "Family importance",
            "atlas_scope": "Family atlas scope",
            "origin_claim": {
                "label": "Family origin",
                "coordinates": [111.0, 41.0],
                "date_or_era": "Deep time",
                "confidence": "moderate",
                "narrative": "Family origin narrative",
            },
            "spread_routes": [],
            "modern_echoes": [],
            "framing_traps": [],
            "linked_reference_slug": "hantavirus-syndrome",
            "linked_story_ids": [],
            "linked_blog_posts": [],
            "citations": [{"id": "family", "short_citation": "Family citation", "url": "https://example.com/family"}],
            "visual_asset_id": "",
            "default_variant_slug": "andes-virus",
            "variants": [
                {
                    "slug": "andes-virus",
                    "name": "Andes virus",
                    "subtitle": "Variant entry",
                    "status": "mixed",
                    "pathogen_type": "Virus",
                    "summary": "Variant summary",
                    "why_it_matters": "Variant importance",
                    "atlas_scope": "Variant scope",
                    "origin_claim": {
                        "label": "Variant origin",
                        "coordinates": [-71.0, -41.5],
                        "date_or_era": "Modern",
                        "confidence": "strong",
                        "narrative": "Variant origin narrative",
                    },
                    "spread_routes": [],
                    "modern_echoes": [],
                    "framing_traps": [],
                    "linked_reference_slug": "hantavirus-syndrome",
                    "linked_story_ids": ["story-1"],
                    "linked_blog_posts": [
                        {
                            "title": "Variant post",
                            "url": "https://example.com/post",
                            "relation": "deep_dive",
                        }
                    ],
                    "citations": [{"id": "variant", "short_citation": "Variant citation", "url": "https://example.com/variant"}],
                    "visual_asset_id": "",
                    "default_variant_slug": "",
                    "variants": [],
                }
            ],
        },
    )
    story_records = [
        {
            "story_id": "story-1",
            "display_title": "Andes cluster",
            "story_url": "https://example.com/story",
            "story_web_path": "stories/andes-cluster.html",
            "latest_update_summary": "Cluster update",
            "current_status_summary": "Active",
        }
    ]
    reference_records = [
        {
            "name": "Hantavirus syndrome",
            "reference_url": "https://example.com/reference",
            "reference_web_path": "reference/hantavirus-syndrome.html",
            "related_stories": [],
        }
    ]

    atlas = build_atlas_records(atlas_entries, story_records, reference_records, ())

    assert atlas[0]["atlas_url"] == "atlas.html?pathogen=hantavirus"
    assert atlas[0]["variant_count"] == 1
    assert atlas[0]["variants"][0]["atlas_url"] == "atlas.html?pathogen=hantavirus&variant=andes-virus"
    assert atlas[0]["variants"][0]["writing_state"] == "direct"
    assert reference_records[0]["atlas_url"] == "atlas.html?pathogen=hantavirus"
