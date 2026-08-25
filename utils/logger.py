"""Centralized logging + session identity for the OrangeHRM automation suite.

One session ID is generated per pytest run (format ``YYYY-MM-DD_HH-MM-SS``)
and threaded through every artifact the run produces:

- ``logs/<session_id>/<test_module>.log``       — per-file log for each test module
- ``artifacts/<session_id>/...``                — Playwright screenshots, videos, traces
- ``reports/<session_id>/allure-results/...``   — Allure JSON results; open with ``allure serve``
- ``reports/<session_id>/report.html``           — self-contained pytest-html report (double-click to open)

Consumers use one entry point::

    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("Creating user: %s", username)

Nothing else in the codebase configures logging directly.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _make_session_id() -> str:
    """One session ID per process, sharable across xdist workers via env var."""
    return os.environ.setdefault(
        "TEST_SESSION_ID",
        datetime.now().strftime("%Y-%m-%d_%H-%M-%S"),
    )


SESSION_ID: str = _make_session_id()

LOGS_ROOT: Path = _ROOT / "logs"
ARTIFACTS_ROOT: Path = _ROOT / "artifacts"
REPORTS_ROOT: Path = _ROOT / "reports"

LOG_DIR: Path = LOGS_ROOT / SESSION_ID
ARTIFACTS_DIR: Path = ARTIFACTS_ROOT / SESSION_ID
REPORTS_DIR: Path = REPORTS_ROOT / SESSION_ID
ALLURE_RESULTS_DIR: Path = REPORTS_DIR / "allure-results"
HTML_REPORT_PATH: Path = REPORTS_DIR / "report.html"

_FORMAT = (
    "%(asctime)s %(levelname)-8s [%(session_id)s] %(name)s: %(message)s"
)
_FORMATTER = logging.Formatter(_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")


class _SessionFilter(logging.Filter):
    """Inject the session ID onto every LogRecord so formatters can render it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = SESSION_ID
        return True


_ROOT_CONFIGURED = False


def _configure_root_once() -> None:
    """Set root level + inject session ID; safe to call repeatedly."""
    global _ROOT_CONFIGURED
    if _ROOT_CONFIGURED:
        return
    root = logging.getLogger()
    if root.level == logging.NOTSET or root.level > logging.DEBUG:
        root.setLevel(logging.DEBUG)
    if not any(isinstance(f, _SessionFilter) for f in root.filters):
        root.addFilter(_SessionFilter())
    _ROOT_CONFIGURED = True


def _handler_key(stem: str) -> str:
    return f"orangehrm::{SESSION_ID}::{stem}"


def attach_for_test_file(test_file_stem: str) -> logging.FileHandler:
    """Attach ``logs/<session>/<stem>.log`` to the root logger for this test file.

    Called from the ``_per_file_log`` autouse fixture in ``conftest.py``.
    """
    _configure_root_once()
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    key = _handler_key(test_file_stem)
    for existing in root.handlers:
        if getattr(existing, "_orangehrm_key", None) == key:
            return existing  # type: ignore[return-value]

    handler = logging.FileHandler(
        LOG_DIR / f"{test_file_stem}.log", mode="a", encoding="utf-8"
    )
    handler.setFormatter(_FORMATTER)
    handler.setLevel(logging.DEBUG)
    handler.addFilter(_SessionFilter())
    handler._orangehrm_key = key  # type: ignore[attr-defined]
    root.addHandler(handler)
    return handler


def get_logger(name: str) -> logging.Logger:
    """Return the shared logger for ``name`` (typically ``__name__``)."""
    _configure_root_once()
    return logging.getLogger(name)


__all__ = [
    "SESSION_ID",
    "LOG_DIR",
    "ARTIFACTS_DIR",
    "REPORTS_DIR",
    "ALLURE_RESULTS_DIR",
    "HTML_REPORT_PATH",
    "get_logger",
    "attach_for_test_file",
]
