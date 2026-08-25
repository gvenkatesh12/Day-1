"""Environment-driven configuration.

Loaded once at import time so tests, fixtures and page objects can all read the
same values without re-parsing the environment.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@dataclass(frozen=True)
class Settings:
    base_url: str
    username: str
    password: str
    browser: str
    headless: bool
    slow_mo: int
    default_timeout_ms: int

    @property
    def login_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/web/index.php/auth/login"


def load_settings() -> Settings:
    username = os.getenv("ORANGEHRM_USERNAME", "Admin")
    password = os.getenv("ORANGEHRM_PASSWORD", "admin123")
    if not username or not password:
        raise RuntimeError(
            "ORANGEHRM_USERNAME and ORANGEHRM_PASSWORD must be set "
            "(see .env.example)."
        )
    return Settings(
        base_url=os.getenv(
            "ORANGEHRM_BASE_URL",
            "https://opensource-demo.orangehrmlive.com",
        ),
        username=username,
        password=password,
        browser=os.getenv("BROWSER", "chrome"),
        headless=_bool("HEADLESS", False),
        slow_mo=_int("SLOW_MO", 0),
        default_timeout_ms=_int("DEFAULT_TIMEOUT", 15_000),
    )
