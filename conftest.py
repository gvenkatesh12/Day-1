"""Pytest + Playwright fixtures for the OrangeHRM suite.

`pytest-playwright` already ships the core `page` / `browser` / `context`
fixtures and CLI flags (--headed, --browser, --slowmo, --screenshot, --video,
--tracing, --output). This file layers on:

* dotenv loading so the suite runs from a plain `pytest` invocation,
* a session identity (utils.logger.SESSION_ID) that routes every log file,
  Playwright artifact, and JUnit report into a single per-run directory,
* a `settings` fixture that centralises environment configuration, and
* a `logged_in_page` fixture that hands tests an already-authenticated page.
"""
from __future__ import annotations

import base64
from pathlib import Path

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Page, expect as pw_expect

import allure

from pages.login_page import LoginPage
from utils.config import Settings, load_settings
from utils.logger import (
    ALLURE_RESULTS_DIR,
    ARTIFACTS_DIR,
    HTML_REPORT_PATH,
    LOG_DIR,
    REPORTS_DIR,
    SESSION_ID,
    attach_for_test_file,
    get_logger,
)
from utils.report import (
    artifact_links_block,
    failure_block,
    testcase_block,
    video_block,
)


load_dotenv(Path(__file__).parent / ".env")


log = get_logger("session")


def pytest_configure(config: pytest.Config) -> None:
    """Bucket every artifact this run produces under the session ID."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    ALLURE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Playwright's expect() default is 5s and is independent of
    # page.set_default_timeout — raise it so toast/redirect assertions get the
    # same window as page operations against the (slow) demo site.
    pw_expect.set_options(timeout=15_000)

    # Redirect pytest-playwright's --output (screenshots, videos, traces).
    config.option.output = str(ARTIFACTS_DIR)
    # Write allure results under the same session bucket so one folder holds
    # everything from a run.
    if not getattr(config.option, "allure_report_dir", None):
        config.option.allure_report_dir = str(ALLURE_RESULTS_DIR)

    # pytest-html: single self-contained file the user can open in a browser
    # without any external tooling.
    if not getattr(config.option, "htmlpath", None):
        config.option.htmlpath = str(HTML_REPORT_PATH)
    config.option.self_contained_html = True

    log.info("Test session started")
    log.info("  session_id      : %s", SESSION_ID)
    log.info("  logs dir        : %s", LOG_DIR)
    log.info("  artifacts       : %s", ARTIFACTS_DIR)
    log.info("  allure results  : %s", ALLURE_RESULTS_DIR)
    log.info("  html report     : %s", HTML_REPORT_PATH)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    log.info(
        "Test session finished (session_id=%s, exitstatus=%s)",
        SESSION_ID,
        exitstatus,
    )


# Remember each test's "call" report so we can enrich it after teardown, once
# pytest-playwright has finished writing screenshots / video / trace to disk.
_CALL_REPORTS: dict[str, pytest.TestReport] = {}


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """Attach Playwright artifacts + the per-file log to both reports.

    Runs on:
    - ``call``     — attach the test-case metadata, log, and root cause
    - ``teardown`` — attach screenshot, video, trace (they were just written)
    """
    outcome = yield
    report = outcome.get_result()

    if report.when == "call":
        _CALL_REPORTS[item.nodeid] = report
        _attach_call_extras(item, report)
    elif report.when == "teardown":
        target = _CALL_REPORTS.pop(item.nodeid, None)
        if target is not None:
            _attach_artifact_extras(item, target)


def _attach_call_extras(item: pytest.Item, report: pytest.TestReport) -> None:
    module_log = LOG_DIR / f"{Path(item.fspath).stem}.log"

    # Allure — log (screenshots/video attached later, during teardown).
    if module_log.exists():
        allure.attach.file(
            str(module_log),
            name=f"{Path(item.fspath).stem}.log",
            attachment_type=allure.attachment_type.TEXT,
        )

    try:
        from pytest_html import extras as html_extras
    except ImportError:
        return

    extra = list(getattr(report, "extras", []))

    # 1) Test Case scenario block — driven by the `testcase` marker on the test.
    marker = item.get_closest_marker("testcase")
    if marker is not None:
        extra.append(html_extras.html(testcase_block(
            sl_no=marker.kwargs.get("sl_no", ""),
            test_id=marker.kwargs.get("id", ""),
            scenario=marker.kwargs.get("scenario", item.name),
            complexity=marker.kwargs.get("complexity", ""),
            app_link=marker.kwargs.get("app_link", ""),
            steps=marker.kwargs.get("steps", []),
            validation=marker.kwargs.get("validation", []),
            expected_result=marker.kwargs.get("expected_result", ""),
            nodeid=item.nodeid,
            session_id=SESSION_ID,
            outcome=report.outcome,
            duration_s=report.duration,
        )))

    # 2) Per-file log.
    if module_log.exists():
        extra.append(html_extras.text(
            module_log.read_text(encoding="utf-8"), name="test log"
        ))

    # 3) Root cause / traceback on failure.
    if report.failed and report.longreprtext:
        extra.append(html_extras.html(failure_block(report.longreprtext)))

    report.extras = extra


def _attach_artifact_extras(item: pytest.Item, report: pytest.TestReport) -> None:
    """Attach Playwright artifacts — safe to call in teardown once they're written."""
    slug = _artifact_slug(item.nodeid)
    test_artifact_dir = ARTIFACTS_DIR / slug
    if not test_artifact_dir.is_dir():
        return

    # Allure — attach every artifact file we know how to type; skip zip (no mapping).
    _ALLURE_SKIP = {".zip"}
    for path in sorted(test_artifact_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() in _ALLURE_SKIP:
            continue
        allure.attach.file(
            str(path),
            name=path.name,
            attachment_type=_attachment_type_for(path.suffix.lower()),
        )

    try:
        from pytest_html import extras as html_extras
    except ImportError:
        return

    extra = list(getattr(report, "extras", []))

    # Screenshots (embedded PNG).
    for path in sorted(test_artifact_dir.iterdir()):
        if path.is_file() and path.suffix.lower() == ".png":
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            extra.append(html_extras.png(data, name=path.name))

    # Video (embedded via base64 data URI in a <video> tag).
    video = test_artifact_dir / "video.webm"
    if video.exists():
        extra.append(html_extras.html(video_block(video)))

    # Artifact locations on disk (trace.zip → link, not inline).
    files = {p.name: p for p in sorted(test_artifact_dir.iterdir()) if p.is_file()}
    if files:
        extra.append(html_extras.html(artifact_links_block(files)))

    report.extras = extra


def _artifact_slug(nodeid: str) -> str:
    """Mirror pytest-playwright's artifact-folder naming for a nodeid."""
    # Example: tests/test_user_management.py::test_create_update_delete_user
    #       -> tests-test-user-management-py-test-create-update-delete-user
    slug = nodeid.replace("::", "-").replace("/", "-").replace("\\", "-")
    slug = slug.replace(".", "-").replace("_", "-")
    return slug.lower()


def _attachment_type_for(suffix: str):
    return {
        ".png": allure.attachment_type.PNG,
        ".jpg": allure.attachment_type.JPG,
        ".jpeg": allure.attachment_type.JPG,
        ".webm": allure.attachment_type.WEBM,
        ".mp4": allure.attachment_type.MP4,
        ".txt": allure.attachment_type.TEXT,
        ".log": allure.attachment_type.TEXT,
        ".html": allure.attachment_type.HTML,
    }.get(suffix, allure.attachment_type.TEXT)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Route pytest outcomes into the logging system so per-file logs capture them."""
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        if report.outcome == "passed":
            log.info(
                "%s %s (%s) in %.2fs",
                report.outcome.upper(),
                report.nodeid,
                report.when,
                report.duration,
            )
        else:
            log.error(
                "%s %s (%s) in %.2fs",
                report.outcome.upper(),
                report.nodeid,
                report.when,
                report.duration,
            )
            if report.longreprtext:
                log.error("failure detail:\n%s", report.longreprtext)


@pytest.fixture(autouse=True)
def _per_file_log(request: pytest.FixtureRequest):
    """Attach `logs/<session>/<test_module>.log` for the duration of the test."""
    stem = Path(request.node.fspath).stem
    attach_for_test_file(stem)
    test_log = get_logger(f"test.{stem}")
    test_log.info("=== START %s ===", request.node.name)
    yield
    test_log.info("=== END   %s ===", request.node.name)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return load_settings()


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, settings: Settings):
    """Extend pytest-playwright's default context args with our base URL."""
    return {
        **browser_context_args,
        "base_url": settings.base_url,
        "viewport": {"width": 1440, "height": 900},
    }


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args, settings: Settings):
    return {
        **browser_type_launch_args,
        "headless": settings.headless,
        "slow_mo": settings.slow_mo,
    }


@pytest.fixture
def page(page: Page, settings: Settings) -> Page:
    page.set_default_timeout(settings.default_timeout_ms)
    return page


@pytest.fixture
def logged_in_page(page: Page, settings: Settings) -> Page:
    login = LoginPage(page)
    login.open(settings.base_url)
    login.login(settings.username, settings.password)
    return page
