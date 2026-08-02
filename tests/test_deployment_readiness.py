import json
import runpy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from web_openness.runner import RunStore

_READINESS = runpy.run_path(str(Path(__file__).parents[1] / "deploy" / "check_readiness.py"))
check_readiness = cast(Any, _READINESS["check_readiness"])
main = cast(Any, _READINESS["main"])


def _deployment(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    site = tmp_path / "site"
    well_known = site / ".well-known"
    well_known.mkdir(parents=True)
    site.joinpath("index.html").write_text(
        """
        <h1>Public web study</h1>
        <p>User-Agent: PublicStudy/1.0</p>
        <p>Source addresses: 192.0.2.10</p>
        <p>We check robots.txt and honor opt-out requests.</p>
        <a href="mailto:research@university.edu">mailto:research@university.edu</a>
        """,
        encoding="utf-8",
    )
    well_known.joinpath("probing.txt").write_text(
        """Canonical: https://scanner.university.edu/.well-known/probing.txt
Contact: mailto:research@university.edu
Expires: 2026-06-01T00:00:00Z
Preferred-Languages: en
Description: Bounded academic public-web measurement.
""",
        encoding="utf-8",
    )
    cease_list = tmp_path / "cease-list.txt"
    cease_list.write_text("", encoding="utf-8")
    state = tmp_path / "runner.sqlite3"
    with RunStore(state):
        pass
    complaints = tmp_path / "complaints.jsonl"
    complaints.write_text("", encoding="utf-8")
    return site, cease_list, state, complaints


def test_readiness_check_passes_without_changing_runner_state(tmp_path: Path) -> None:
    site, cease_list, state, complaints = _deployment(tmp_path)

    failures = check_readiness(
        site_dir=site,
        cease_list_path=cease_list,
        state_path=state,
        complaint_log_path=complaints,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert failures == []
    with RunStore(state) as store:
        assert store.global_stop_requested() is False


def test_readiness_reports_placeholders_expiry_stop_and_bad_complaint(tmp_path: Path) -> None:
    site, cease_list, state, complaints = _deployment(tmp_path)
    site.joinpath("index.html").write_text("REPLACE_USER_AGENT", encoding="utf-8")
    site.joinpath(".well-known/probing.txt").write_text(
        """Canonical: https://scanner.example.org/.well-known/probing.txt
Contact: mailto:research@example.org
Expires: 2025-01-01T00:00:00Z
Preferred-Languages: en
Description: Example.
""",
        encoding="utf-8",
    )
    complaints.write_text('{"domain":"example.org"}\n', encoding="utf-8")
    with RunStore(state) as store:
        store.set_global_stop(True)

    failures = check_readiness(
        site_dir=site,
        cease_list_path=cease_list,
        state_path=state,
        complaint_log_path=complaints,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert any("placeholders" in failure for failure in failures)
    assert any("not in the future" in failure for failure in failures)
    assert any("global stop is active" in failure for failure in failures)
    assert any("complaint log line 1 is missing fields" in failure for failure in failures)


def test_readiness_cli_returns_machine_readable_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing"

    exit_code = main(
        [
            "--site-dir",
            str(missing),
            "--cease-list",
            str(missing / "cease.txt"),
            "--state",
            str(missing / "state.sqlite3"),
            "--complaint-log",
            str(missing / "complaints.jsonl"),
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["ready"] is False
    assert output["failures"]
