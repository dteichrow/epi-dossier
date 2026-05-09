from pathlib import Path

from src.emailer import build_email_message
from src.utils import EmailConfig


def test_build_email_message_includes_subject_and_body(tmp_path: Path):
    dossier = tmp_path / "latest.md"
    dossier.write_text("# Test Dossier\n\nBody", encoding="utf-8")
    config = EmailConfig(
        enabled=True,
        username="devinteichrow@gmail.com",
        from_email="devinteichrow@gmail.com",
        to_email="devinteichrow@gmail.com",
    )

    message = build_email_message(
        config=config,
        dossier_path=dossier,
        target_date="2026-05-04",
        generated_at="2026-05-04T08:05",
    )

    assert message["Subject"] == "Daily Epidemiology Dossier | 2026-05-04"
    assert "Body" in message.get_content()
