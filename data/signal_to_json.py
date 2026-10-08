import json
import re
from collections import defaultdict
from pathlib import Path


# Folder containing the original scanner JSON snapshots
SNAPSHOT_ROOT = Path("data/snapshots/2026-10-04")

# Folder where one JSON file per signal will be written
OUTPUT_ROOT = Path("data/analysis/top500-2026-10-04/signals")


def safe_filename(signal: str) -> str:
    """Create a safe filename while keeping the signal name recognizable."""
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", signal) + ".json"


def main() -> None:
    # Find every original JSON snapshot
    snapshot_paths = sorted(SNAPSHOT_ROOT.rglob("*.json"))

    if not snapshot_paths:
        raise FileNotFoundError(
            f"No JSON snapshots found in: {SNAPSHOT_ROOT}"
        )

    # Keep one snapshot per domain.
    # If a domain was scanned more than once, keep the newest snapshot.
    latest_snapshots = {}

    for snapshot_path in snapshot_paths:
        with snapshot_path.open(encoding="utf-8") as file:
            snapshot = json.load(file)

        domain = snapshot.get("domain")
        completed_at = str(snapshot.get("completed_at", ""))

        if not domain:
            continue

        previous = latest_snapshots.get(domain)

        if previous is None or completed_at > previous[0]:
            latest_snapshots[domain] = (completed_at, snapshot)

    # Group complete observation objects by signal
    observations_by_signal = defaultdict(list)

    for domain, (completed_at, snapshot) in latest_snapshots.items():
        observations = snapshot.get("observations", {})

        for signal, observation in observations.items():
            observations_by_signal[signal].append(
                {
                    "domain": domain,
                    "run_id": snapshot.get("run_id"),
                    "completed_at": completed_at,

                    # Preserve the original observation exactly
                    "observation": observation,
                }
            )

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    # Create one JSON file for each signal
    for signal, domain_records in sorted(observations_by_signal.items()):
        domain_records.sort(key=lambda record: record["domain"])

        output = {
            "signal": signal,
            "group": signal.split(".", 1)[0].title(),
            "domain_count": len(domain_records),
            "domains": domain_records,
        }

        output_path = OUTPUT_ROOT / safe_filename(signal)

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(output, file, indent=2, ensure_ascii=False)
            file.write("\n")

    print(f"Snapshots found: {len(snapshot_paths)}")
    print(f"Unique domains included: {len(latest_snapshots)}")
    print(f"Signal files created: {len(observations_by_signal)}")
    print(f"Output directory: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()