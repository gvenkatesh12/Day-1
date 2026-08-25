"""Helpers for rendering rich content into the pytest-html report.

Each helper returns an HTML string that is attached to a test row via
``pytest_html.extras.html(...)`` from ``conftest.pytest_runtest_makereport``.
Keeping the markup here keeps ``conftest.py`` focused on wiring.
"""
from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Iterable, Mapping


_STYLE = """
<style>
  .tc-block { font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
              line-height: 1.4; margin: 0.5rem 0 1rem 0; }
  .tc-block h4 { margin: 0.75rem 0 0.25rem; color: #24292e; }
  .tc-block dl { display: grid; grid-template-columns: 8rem 1fr;
                 column-gap: 0.75rem; row-gap: 0.25rem; margin: 0.25rem 0; }
  .tc-block dt { font-weight: 600; color: #57606a; }
  .tc-block dd { margin: 0; }
  .tc-block ol { margin: 0.25rem 0 0 1.25rem; padding: 0; }
  .tc-block ol li { margin-bottom: 0.15rem; }
  .tc-block pre { background: #f6f8fa; padding: 0.75rem; border-radius: 6px;
                  overflow-x: auto; white-space: pre-wrap; word-wrap: break-word;
                  font-size: 0.85rem; }
  .tc-block .tc-fail { color: #b31d28; }
  .tc-video { max-width: 720px; width: 100%; margin-top: 0.25rem;
              border-radius: 6px; }
</style>
"""


def testcase_block(
    *,
    sl_no: int | str,
    test_id: str,
    scenario: str,
    complexity: str,
    app_link: str,
    steps: Iterable[str],
    validation: Iterable[str],
    expected_result: str,
    nodeid: str,
    session_id: str,
    outcome: str,
    duration_s: float,
) -> str:
    """Render the full Test Case / Steps / Validation / Expected-Result section."""
    steps_html = "\n".join(f"    <li>{html.escape(s)}</li>" for s in steps)
    validation_html = "\n".join(f"    <li>{html.escape(v)}</li>" for v in validation)
    app_link_html = (
        f'<a href="{html.escape(app_link)}" target="_blank" rel="noopener">'
        f"{html.escape(app_link)}</a>"
    )
    return f"""
{_STYLE}
<div class="tc-block">
  <h4>Test Case</h4>
  <dl>
    <dt>SL No</dt>       <dd>{html.escape(str(sl_no))}</dd>
    <dt>ID</dt>          <dd>{html.escape(test_id)}</dd>
    <dt>Scenario</dt>    <dd>{html.escape(scenario)}</dd>
    <dt>Complexity</dt>  <dd>{html.escape(complexity)}</dd>
    <dt>App Link</dt>    <dd>{app_link_html}</dd>
    <dt>Node ID</dt>     <dd><code>{html.escape(nodeid)}</code></dd>
    <dt>Session</dt>     <dd><code>{html.escape(session_id)}</code></dd>
    <dt>Outcome</dt>     <dd>{html.escape(outcome.upper())} ({duration_s:.2f}s)</dd>
  </dl>
  <h4>Steps to Reproduce</h4>
  <ol>
{steps_html}
  </ol>
  <h4>Validation</h4>
  <ul>
{validation_html}
  </ul>
  <h4>Expected Result</h4>
  <p>{html.escape(expected_result)}</p>
</div>
""".strip()


def video_block(video_path: Path, *, mime: str = "video/webm") -> str:
    """Inline video as an HTML5 <video> tag using a base64 data URI."""
    data = base64.b64encode(video_path.read_bytes()).decode("ascii")
    return (
        f'<div class="tc-block"><h4>Video proof</h4>'
        f'<video controls class="tc-video">'
        f'<source src="data:{mime};base64,{data}" type="{mime}">'
        f"Your browser cannot play the embedded {mime} video."
        f"</video></div>"
    )


def failure_block(longrepr: str) -> str:
    """Render the failure traceback as a 'root cause' block."""
    return (
        '<div class="tc-block tc-fail"><h4>Root cause / traceback</h4>'
        f"<pre>{html.escape(longrepr)}</pre></div>"
    )


def artifact_links_block(files: Mapping[str, Path]) -> str:
    """Render a small table of artifact file paths (screenshot / video / trace)."""
    rows = "\n".join(
        f"    <dt>{html.escape(label)}</dt><dd><code>{html.escape(str(p))}</code></dd>"
        for label, p in files.items()
    )
    return (
        '<div class="tc-block"><h4>Artifacts on disk</h4>'
        f"<dl>{rows}</dl></div>"
    )
