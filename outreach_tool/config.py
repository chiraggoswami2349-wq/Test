from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Set

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT_DIR / "output"

COUNTRY_TIMEZONE_MAP = {
    "india": "Asia/Kolkata",
    "australia": "Australia/Melbourne",
    "uae": "Asia/Dubai",
    "uk": "Europe/London",
    "usa": "America/New_York",
}

ALLOWED_SENDERS_DEFAULT = {
    "astha@cybernara.net",
    "chirag@cybernara.com",
    "chirag@cybernara.net",
}

REQUIRED_COLUMNS = {
    "name",
    "company",
    "sender",
    "country",
    "subject",
    "body",
    "email1",
}

OPTIONAL_EMAIL_COLUMNS = ["email2", "email3"]


@dataclass
class AppSecrets:
    tenant_id: str
    client_id: str
    client_secret: str
    verifalia_username: str | None = None
    verifalia_password: str | None = None


@dataclass
class CampaignSettings:
    verification_enabled: bool = True
    verification_quality: str = "High"
    max_emails_per_run: int = 50
    hard_max_emails_per_run: int = 50
    delay_min_seconds: int = 300
    delay_max_seconds: int = 720
    defer_outside_business_hours: bool = True
    stop_on_verifalia_credits_exhausted: bool = True
    sender_allow_list: Set[str] = field(default_factory=lambda: set(ALLOWED_SENDERS_DEFAULT))
    send_as_html: bool = False

    def normalize(self) -> "CampaignSettings":
        self.max_emails_per_run = max(1, min(self.max_emails_per_run, self.hard_max_emails_per_run))
        self.delay_min_seconds = max(0, self.delay_min_seconds)
        self.delay_max_seconds = max(self.delay_min_seconds, self.delay_max_seconds)
        self.verification_quality = self.verification_quality.title()
        return self


def load_env(env_path: str | None = None) -> None:
    if env_path:
        load_dotenv(env_path)
    else:
        load_dotenv(ROOT_DIR / ".env")
        load_dotenv()


def load_secrets() -> AppSecrets:
    missing = [
        key
        for key in ("TENANT_ID", "CLIENT_ID", "CLIENT_SECRET")
        if not os.getenv(key)
    ]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return AppSecrets(
        tenant_id=os.environ["TENANT_ID"],
        client_id=os.environ["CLIENT_ID"],
        client_secret=os.environ["CLIENT_SECRET"],
        verifalia_username=os.getenv("VERIFALIA_USERNAME"),
        verifalia_password=os.getenv("VERIFALIA_PASSWORD"),
    )
