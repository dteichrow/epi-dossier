from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path

from .utils import EmailConfig, resolve_email_password


def send_dossier_email(
    config: EmailConfig,
    dossier_path: Path,
    target_date: str,
    generated_at: str,
    logger: logging.Logger,
) -> bool:
    if not config.enabled:
        return False

    password = resolve_email_password(config)
    if not all([config.username, config.from_email, config.to_email, password]):
        logger.warning("Email delivery skipped: email config is incomplete.")
        return False

    message = build_email_message(
        config=config,
        dossier_path=dossier_path,
        target_date=target_date,
        generated_at=generated_at,
    )

    try:
        if config.use_ssl:
            with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port) as server:
                server.login(config.username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
                server.starttls()
                server.login(config.username, password)
                server.send_message(message)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Email delivery failed: %s", exc)
        return False

    logger.info("Emailed dossier to %s", config.to_email)
    return True


def build_email_message(
    config: EmailConfig,
    dossier_path: Path,
    target_date: str,
    generated_at: str,
) -> EmailMessage:
    body = dossier_path.read_text(encoding="utf-8")
    message = EmailMessage()
    message["Subject"] = f"{config.subject_prefix} | {target_date}"
    message["From"] = config.from_email
    message["To"] = config.to_email
    message.set_content(
        "\n".join(
            [
                f"Date: {target_date}",
                f"Generated at: {generated_at}",
                "",
                body,
            ]
        )
    )
    return message
