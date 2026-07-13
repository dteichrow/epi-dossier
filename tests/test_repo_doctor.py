from __future__ import annotations

from scripts import repo_doctor
from src.outbreak_dashboard_quality import DashboardQualityIssue


def test_repo_doctor_allows_expected_dashboard_rebuild(monkeypatch) -> None:
    monkeypatch.setattr(
        repo_doctor,
        "run_outbreak_dashboard_quality_checks",
        lambda: [
            DashboardQualityIssue(
                "error",
                "story_test",
                "cases",
                "Generated story page dashboard does not match the current snapshot policy.",
            )
        ],
    )

    checks = repo_doctor.check_outbreak_dashboard_quality("epi-dossier")

    assert len(checks) == 1
    assert checks[0].status == "warn"
    assert "strict QA runs after the public build" in checks[0].detail


def test_repo_doctor_blocks_non_render_dashboard_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        repo_doctor,
        "run_outbreak_dashboard_quality_checks",
        lambda: [DashboardQualityIssue("error", "story_test", "cases", "Dashboard override is missing source_url.")],
    )

    checks = repo_doctor.check_outbreak_dashboard_quality("epi-dossier")

    assert len(checks) == 1
    assert checks[0].status == "error"
