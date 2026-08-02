import csv
import json
import os
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from web_openness.models import DomainSnapshot, ObservationOutcome
from web_openness.schema import load_domain_snapshot_json


@dataclass(frozen=True, slots=True)
class AnalysisExport:
    runs_path: Path
    observations_path: Path
    changes_path: Path
    summary_path: Path


def export_analysis(snapshot_root: Path, output_root: Path) -> AnalysisExport:
    """Validate snapshots and export small, analysis-ready tables."""

    snapshots = _load_snapshots(snapshot_root)
    if not snapshots:
        raise ValueError(f"no valid snapshot JSON files found under {snapshot_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    runs_path = output_root / "runs.csv"
    observations_path = output_root / "observations.csv"
    changes_path = output_root / "changes.csv"
    summary_path = output_root / "summary.json"

    outcome_counts: Counter[str] = Counter()
    key_outcomes: dict[str, Counter[str]] = defaultdict(Counter)
    run_rows: list[dict[str, object]] = []
    observation_rows: list[dict[str, object]] = []
    for snapshot in snapshots:
        run_outcomes = Counter(
            observation.outcome.value for observation in snapshot.observations.values()
        )
        browser_network = snapshot.observations.get("browser.network_summary")
        browser_requests = 0
        if browser_network is not None and isinstance(browser_network.value, dict):
            raw_requests = browser_network.value.get("requests")
            if isinstance(raw_requests, int):
                browser_requests = raw_requests
        run_rows.append(
            {
                "run_id": snapshot.run_id,
                "domain": snapshot.domain,
                "origin": snapshot.origin,
                "started_at": snapshot.started_at.isoformat(),
                "completed_at": snapshot.completed_at.isoformat(),
                "collector_version": snapshot.collector_version,
                "http_requests": snapshot.request_count,
                "browser_requests": browser_requests,
                "observed": run_outcomes[ObservationOutcome.OBSERVED.value],
                "no_evidence": run_outcomes[ObservationOutcome.NO_EVIDENCE.value],
                "skipped": run_outcomes[ObservationOutcome.SKIPPED.value],
                "errors": run_outcomes[ObservationOutcome.ERROR.value],
                "probe_errors": len(snapshot.errors),
            }
        )
        for key, observation in sorted(snapshot.observations.items()):
            outcome_counts[observation.outcome.value] += 1
            key_outcomes[key][observation.outcome.value] += 1
            observation_rows.append(
                {
                    "run_id": snapshot.run_id,
                    "domain": snapshot.domain,
                    "completed_at": snapshot.completed_at.isoformat(),
                    "signal": key,
                    "outcome": observation.outcome.value,
                    "confidence": observation.confidence.value,
                    "confidence_score": observation.confidence_score,
                    "value_json": _json_value(observation.value),
                    "method": observation.method,
                    "evidence_count": len(observation.evidence),
                }
            )

    change_rows = _longitudinal_changes(snapshots)
    _write_csv(runs_path, run_rows)
    _write_csv(observations_path, observation_rows)
    _write_csv(
        changes_path,
        change_rows,
        fieldnames=(
            "domain",
            "signal",
            "previous_run_id",
            "current_run_id",
            "previous_completed_at",
            "current_completed_at",
            "previous_outcome",
            "current_outcome",
            "previous_value_json",
            "current_value_json",
            "changed",
        ),
    )

    changed = sum(row["changed"] is True for row in change_rows)
    summary = {
        "snapshot_count": len(snapshots),
        "domain_count": len({snapshot.domain for snapshot in snapshots}),
        "signal_count": len(key_outcomes),
        "outcomes": dict(sorted(outcome_counts.items())),
        "signal_outcomes": {
            key: dict(sorted(counts.items())) for key, counts in sorted(key_outcomes.items())
        },
        "longitudinal": {
            "comparison_count": len(change_rows),
            "changed_count": changed,
            "unchanged_count": len(change_rows) - changed,
        },
    }
    _write_text(summary_path, f"{json.dumps(summary, indent=2, sort_keys=True)}\n")
    return AnalysisExport(runs_path, observations_path, changes_path, summary_path)


def _load_snapshots(root: Path) -> list[DomainSnapshot]:
    snapshots: list[DomainSnapshot] = []
    for path in sorted(root.rglob("*.json")):
        try:
            snapshots.append(load_domain_snapshot_json(path.read_text(encoding="utf-8")))
        except Exception as exc:
            raise ValueError(f"invalid snapshot {path}: {exc}") from exc
    return sorted(
        snapshots, key=lambda snapshot: (snapshot.domain, snapshot.completed_at, snapshot.run_id)
    )


def _longitudinal_changes(snapshots: list[DomainSnapshot]) -> list[dict[str, object]]:
    by_domain: dict[str, list[DomainSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        by_domain[snapshot.domain].append(snapshot)

    rows: list[dict[str, object]] = []
    for domain, domain_snapshots in sorted(by_domain.items()):
        if len(domain_snapshots) < 2:
            continue
        previous, current = domain_snapshots[-2:]
        for signal in sorted(previous.observations.keys() & current.observations.keys()):
            old = previous.observations[signal]
            new = current.observations[signal]
            old_value = _json_value(old.value)
            new_value = _json_value(new.value)
            rows.append(
                {
                    "domain": domain,
                    "signal": signal,
                    "previous_run_id": previous.run_id,
                    "current_run_id": current.run_id,
                    "previous_completed_at": previous.completed_at.isoformat(),
                    "current_completed_at": current.completed_at.isoformat(),
                    "previous_outcome": old.outcome.value,
                    "current_outcome": new.outcome.value,
                    "previous_value_json": old_value,
                    "current_value_json": new_value,
                    "changed": old.outcome != new.outcome or old_value != new_value,
                }
            )
    return rows


def _json_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _write_csv(
    path: Path,
    rows: list[dict[str, object]],
    *,
    fieldnames: tuple[str, ...] | None = None,
) -> None:
    if fieldnames is None:
        if not rows:
            raise ValueError(f"cannot infer columns for empty export {path.name}")
        fieldnames = tuple(rows[0])
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _write_text(path: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
