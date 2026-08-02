import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from web_openness.analysis import export_analysis
from web_openness.models import Confidence, DomainSnapshot, Observation, ObservationOutcome
from web_openness.storage import write_snapshot


def _snapshot(domain: str, run_id: str, completed_at: datetime, value: bool) -> DomainSnapshot:
    return DomainSnapshot(
        run_id=run_id,
        domain=domain,
        origin=f"https://{domain}",
        started_at=completed_at - timedelta(seconds=1),
        completed_at=completed_at,
        collector_version="test",
        request_count=2,
        observations={
            "crawler.robots_exists": Observation(
                value=value,
                outcome=ObservationOutcome.OBSERVED,
                confidence=Confidence.CONFIRMED,
                confidence_score=1.0,
                method="fixture",
            ),
            "browser.navigation": Observation(
                value=None,
                outcome=ObservationOutcome.SKIPPED,
                confidence=Confidence.UNKNOWN,
                confidence_score=0.0,
                method="disabled",
            ),
        },
        requests=[],
    )


def test_analysis_export_writes_long_form_and_longitudinal_outputs(tmp_path: Path) -> None:
    snapshots = tmp_path / "snapshots"
    base = datetime(2026, 1, 1, tzinfo=UTC)
    write_snapshot(_snapshot("example.org", "run-1", base, False), snapshots)
    write_snapshot(_snapshot("example.org", "run-2", base + timedelta(days=1), True), snapshots)
    write_snapshot(_snapshot("example.net", "run-3", base, False), snapshots)

    exported = export_analysis(snapshots, tmp_path / "analysis")
    with exported.runs_path.open(newline="", encoding="utf-8") as handle:
        runs = list(csv.DictReader(handle))
    with exported.observations_path.open(newline="", encoding="utf-8") as handle:
        observations = list(csv.DictReader(handle))
    with exported.changes_path.open(newline="", encoding="utf-8") as handle:
        changes = list(csv.DictReader(handle))
    summary = json.loads(exported.summary_path.read_text(encoding="utf-8"))

    assert len(runs) == 3
    assert len(observations) == 6
    assert runs[0]["http_requests"] == "2"
    robots_change = next(row for row in changes if row["signal"] == "crawler.robots_exists")
    assert robots_change["changed"] == "True"
    assert summary["snapshot_count"] == 3
    assert summary["domain_count"] == 2
    assert summary["outcomes"] == {"observed": 3, "skipped": 3}


def test_analysis_export_rejects_non_snapshot_json(tmp_path: Path) -> None:
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    (snapshots / "bad.json").write_text('{"not": "a snapshot"}\n', encoding="utf-8")

    try:
        export_analysis(snapshots, tmp_path / "analysis")
    except ValueError as exc:
        assert "invalid snapshot" in str(exc)
    else:
        raise AssertionError("invalid snapshot was accepted")
