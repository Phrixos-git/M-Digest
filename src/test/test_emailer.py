from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from info_agent.emailer import EmailConfig, load_email_config_from_env, send_report_email


class _Smtp:
    instance = None

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.started_tls = False
        self.login_args = None
        self.message = None
        type(self).instance = self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message) -> None:
        self.message = message


class EmailerTest(unittest.TestCase):
    def test_loads_gmail_defaults_and_recipients(self) -> None:
        environment = {
            "INFO_AGENT_SMTP_USERNAME": "sender@gmail.com",
            "INFO_AGENT_SMTP_PASSWORD": "secret",
            "INFO_AGENT_EMAIL_TO": "a@example.com, b@example.com",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = load_email_config_from_env()
        self.assertEqual(config.sender, "sender@gmail.com")
        self.assertEqual(config.smtp_port, 587)
        self.assertEqual(config.recipients, ("a@example.com", "b@example.com"))
        self.assertTrue(config.use_starttls)

    def test_loads_ssl_and_custom_port(self) -> None:
        environment = {
            "INFO_AGENT_SMTP_HOST": "mail.example.com",
            "INFO_AGENT_SMTP_SSL": "true",
            "INFO_AGENT_SMTP_PORT": "2465",
            "INFO_AGENT_EMAIL_FROM": "sender@example.com",
            "INFO_AGENT_EMAIL_TO": "to@example.com",
        }
        with patch.dict(os.environ, environment, clear=True):
            config = load_email_config_from_env()
        self.assertTrue(config.use_ssl)
        self.assertEqual(config.smtp_port, 2465)

    def test_rejects_missing_or_invalid_environment(self) -> None:
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "SMTP_USERNAME"):
            load_email_config_from_env()
        environment = {
            "INFO_AGENT_SMTP_HOST": "mail.example.com",
            "INFO_AGENT_EMAIL_FROM": "from@example.com",
            "INFO_AGENT_EMAIL_TO": "to@example.com",
            "INFO_AGENT_SMTP_PORT": "bad",
        }
        with patch.dict(os.environ, environment, clear=True), self.assertRaisesRegex(ValueError, "integer"):
            load_email_config_from_env()

    def test_sends_markdown_attachment_with_starttls_and_login(self) -> None:
        config = EmailConfig(
            "mail.example.com", 587, "from@example.com", ("to@example.com",),
            username="user", password="pass",
        )
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            report.write_text("# Report", encoding="utf-8")
            with patch("info_agent.emailer.smtplib.SMTP", _Smtp):
                send_report_email(report, "2026-07-18", config)
        smtp = _Smtp.instance
        self.assertTrue(smtp.started_tls)
        self.assertEqual(smtp.login_args, ("user", "pass"))
        self.assertEqual(smtp.message["Subject"], "2026-07-18 今日のニュース")
        self.assertEqual(smtp.message.get_payload()[1].get_filename(), "report.md")

    def test_ssl_does_not_start_starttls_or_login_without_credentials(self) -> None:
        config = EmailConfig("mail.example.com", 465, "from@example.com", ("to@example.com",), use_ssl=True)
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            report.write_text("report", encoding="utf-8")
            with patch("info_agent.emailer.smtplib.SMTP_SSL", _Smtp):
                send_report_email(report, "2026-07-18", config)
        self.assertFalse(_Smtp.instance.started_tls)
        self.assertIsNone(_Smtp.instance.login_args)


if __name__ == "__main__":
    unittest.main()
