# Day 1 — OrangeHRM Playwright Automation

End-to-end automation for the OrangeHRM demo site covering the
**Create → Verify → Edit → Verify → Delete → Verify** user-management flow.

Stack: Python + Playwright + pytest, Page Object Model, environment-driven
configuration, screenshots / video / traces on failure.

## Project structure

```
Day 1/
├── tests/
│   └── test_user_management.py     # end-to-end scenario
├── pages/
│   ├── base_page.py                # shared page behaviour
│   ├── login_page.py               # login screen
│   └── admin_user_page.py          # Admin → User Management
├── utils/
│   ├── config.py                   # env-driven settings
│   ├── logger.py                   # centralized logger + session ID
│   └── test_data.py                # unique-value generators + data classes
├── logs/<session_id>/                       # per-test-file .log written per run
├── artifacts/<session_id>/                  # screenshots / video / trace on failure
├── reports/<session_id>/report.html         # pytest-html — double-click to open in browser
├── reports/<session_id>/allure-results/     # Allure JSON — open with `allure serve`
├── conftest.py                     # pytest + Playwright fixtures
├── pytest.ini                      # pytest configuration
├── requirements.txt
├── .env.example
└── README.md
```

## Setup

```powershell
# 1. From the Day 1 folder, create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install Playwright browsers
playwright install

# 4. Configure credentials
copy .env.example .env
# then edit .env with your ORANGEHRM_USERNAME / ORANGEHRM_PASSWORD
```

## Running tests

If the virtualenv is activated, `pytest` is on PATH. If it isn't, call it
through the interpreter (`& ".\.venv\Scripts\python.exe" -m pytest ...`).

```powershell
# Default (headless, chromium)
pytest

# Headed (watch the browser)
pytest --headed

# A specific browser
pytest --browser chrome

# Single test file
pytest tests/test_user_management.py

# Single test by name
pytest tests/test_user_management.py::test_create_update_delete_user

# Only the smoke-tagged tests
pytest -m smoke
```

### Session ID

At the start of every pytest run, `utils/logger.py` generates a unique
session ID in `YYYY-MM-DD_HH-MM-SS` form (for example
`2026-08-21_17-46-00`). Every artifact this run produces is bucketed under
that ID:

| kind           | path                                                   |
| -------------- | ------------------------------------------------------ |
| per-file log   | `logs/<session_id>/<test_module>.log`                  |
| HTML report    | `reports/<session_id>/report.html`                     |
| Allure results | `reports/<session_id>/allure-results/*.json`           |
| screenshots    | `artifacts/<session_id>/<test-name>/*.png`             |
| video/trace    | `artifacts/<session_id>/<test-name>/*.webm/zip`        |

Every log record also includes the session ID inline
(`[2026-08-21_17-46-00] pages.admin_user_page: ...`) so cross-referencing
logs against artifacts is trivial. The ID is available in code via
`from utils.logger import SESSION_ID`.

### Centralized logging

`utils/logger.py` is the one logging entry point. Page objects and tests
call `get_logger(__name__)` and use standard `log.info(...)` /
`log.error(...)` calls — there is no per-page logging configuration.

```python
from utils.logger import get_logger

log = get_logger(__name__)
log.info("Creating user: %s", username)
```

Test-level start/end markers are added automatically by the `_per_file_log`
autouse fixture in `conftest.py`.

### HTML report (browser, no extra install)

`pytest-html` writes a single self-contained
`reports/<session_id>/report.html` on every run. The last line of the
pytest output prints the exact `file://` URL — click it, or open it from
Explorer.

Each row expands to show:

- **Test Case** — ID / name / node ID / session ID / outcome / duration
- **Test Plan** — the intent of the test (from the `@pytest.mark.testcase(plan=...)` marker)
- **Steps to Reproduce** — the numbered manual steps (from the same marker)
- **Screenshot** — the Playwright screenshot, embedded inline
- **Video proof** — an inline HTML5 `<video>` player with the recorded run
- **Artifacts on disk** — full paths to screenshot / video / trace so you can
  open them in the OS or feed the trace to `playwright show-trace`
- **Test log** — the full per-file log as an expandable text attachment
- **Root cause / traceback** — the failing assertion + Playwright call log
  (only rendered on failure)

Add new tests with the same rich rendering by decorating them:

```python
@pytest.mark.testcase(
    id="TC-ADMIN-002",
    name="Non-admin user cannot access User Management",
    plan="Verify authorization by...",
    steps=["Log in as ESS user.", "Navigate to /admin/…", "Assert 403/redirect."],
)
def test_ess_user_cannot_access_admin(...): ...
```

```powershell
# From project root, print the URL for the most recent run
$latest = (Get-ChildItem .\reports | Sort-Object LastWriteTime -Descending | Select-Object -First 1).Name
"file:///$($PWD.Path -replace '\\','/')/reports/$latest/report.html".Replace(' ', '%20')
```

### Allure report

`allure-pytest` writes JSON results under
`reports/<session_id>/allure-results/` on every run. The suite adds:

- `@allure.epic("OrangeHRM") / feature / story / severity` on the test, so
  the report has a proper hierarchy
- `@allure.step(...)` on major page-object actions
  (`open`, `create_user`, `edit_user`, `delete_user`, …)
- Automatic attachments **on failure**: the per-file log, the failure
  screenshot, the recorded video, and the Playwright trace zip — wired in
  `conftest.pytest_runtest_makereport`

Install the Allure CLI once (JVM-based, separate from the Python package):

```powershell
# Any of these works — pick what fits your machine
scoop install allure
# choco install allure-commandline
# npm install -g allure-commandline
```

Then, from the project root, render the HTML report for the latest run:

```powershell
$latest = (Get-ChildItem .\reports | Sort-Object LastWriteTime -Descending | Select-Object -First 1).Name
allure serve .\reports\$latest\allure-results
```

`allure serve` boots a local web server and opens the report in your browser.
To generate a static bundle instead of a live server:

```powershell
allure generate .\reports\$latest\allure-results -o .\reports\$latest\allure-report --clean
```

### Artifacts on failure

Screenshots, videos, and traces land under
`artifacts/<session_id>/<test-name>/` and are also attached to the Allure
report automatically. To open a trace directly:

```powershell
playwright show-trace artifacts\<session_id>\<test-name>\trace.zip
```

## Debugging

```powershell
# Playwright Inspector (step through actions)
$env:PWDEBUG=1; pytest --headed; Remove-Item Env:PWDEBUG

# Slow the browser down so you can watch it work
$env:SLOW_MO=500; pytest --headed; Remove-Item Env:SLOW_MO

# Tail the log for the test file you just ran
Get-Content .\logs\test_user_management.log -Tail 30
```

## Notes on the demo site

OrangeHRM's demo credentials (`Admin` / `admin123`) are public. Treat this
project as a template — for any non-demo environment, put real credentials in
`.env` (which is `.gitignore`d) or a secret manager, never in source.
