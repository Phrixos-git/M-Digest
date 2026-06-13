from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: str
    smtp_port: int
    sender: str
    recipients: tuple[str, ...]
    subject: str = ""
    username: str = ""
    password: str = ""
    use_starttls: bool = True
    use_ssl: bool = False


def load_email_config_from_env() -> EmailConfig:
    smtp_host = os.environ.get("INFO_AGENT_SMTP_HOST", "smtp.gmail.com").strip()
    sender = os.environ.get("INFO_AGENT_EMAIL_FROM", "").strip()
    recipients = _split_recipients(os.environ.get("INFO_AGENT_EMAIL_TO", ""))
    username = os.environ.get("INFO_AGENT_SMTP_USERNAME", "").strip()
    password = os.environ.get("INFO_AGENT_SMTP_PASSWORD", "")
    use_ssl = _as_bool(os.environ.get("INFO_AGENT_SMTP_SSL", "false"))

    if not sender and username:
        sender = username

    gmail_smtp = _is_gmail_smtp(smtp_host)
    missing: list[str] = []
    if gmail_smtp and not username:
        missing.append("INFO_AGENT_SMTP_USERNAME")
    if gmail_smtp and not password:
        missing.append("INFO_AGENT_SMTP_PASSWORD")
    if not sender and not gmail_smtp:
        missing.append("INFO_AGENT_EMAIL_FROM")
    if not recipients:
        missing.append("INFO_AGENT_EMAIL_TO")
    if missing:
        raise ValueError(f"missing email environment variables: {', '.join(missing)}")

    return EmailConfig(
        smtp_host=smtp_host,
        smtp_port=_smtp_port(use_ssl),
        sender=sender,
        recipients=recipients,
        subject=os.environ.get("INFO_AGENT_EMAIL_SUBJECT", "").strip(),
        username=username,
        password=password,
        use_starttls=_as_bool(os.environ.get("INFO_AGENT_SMTP_STARTTLS", "true")),
        use_ssl=use_ssl,
    )


def send_report_email(report_path: Path, report_date: str, config: EmailConfig) -> None:
    report_text = report_path.read_text(encoding="utf-8")
    message = EmailMessage()
    message["Subject"] = config.subject or f"{report_date} 今日のニュース"
    message["From"] = config.sender
    message["To"] = ", ".join(config.recipients)
    message.set_content("今日のニュースです")
    message.add_attachment(
        report_text,
        subtype="markdown",
        filename=report_path.name,
    )

    smtp_class = smtplib.SMTP_SSL if config.use_ssl else smtplib.SMTP
    with smtp_class(config.smtp_host, config.smtp_port, timeout=30) as smtp:
        if config.use_starttls and not config.use_ssl:
            smtp.starttls()
        if config.username or config.password:
            smtp.login(config.username, config.password)
        smtp.send_message(message)


def _smtp_port(use_ssl: bool) -> int:
    raw_port = os.environ.get("INFO_AGENT_SMTP_PORT", "").strip()
    if raw_port:
        try:
            return int(raw_port)
        except ValueError as exc:
            raise ValueError("INFO_AGENT_SMTP_PORT must be an integer") from exc
    return 465 if use_ssl else 587


def _split_recipients(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _as_bool(value: str) -> bool:
    return value.strip().casefold() not in {"false", "no", "0", "off"}


def _is_gmail_smtp(host: str) -> bool:
    return host.casefold() == "smtp.gmail.com"
