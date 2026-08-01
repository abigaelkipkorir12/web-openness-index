import os
import tempfile
from pathlib import Path

from web_openness.models import DomainSnapshot


def write_snapshot(snapshot: DomainSnapshot, root: Path) -> Path:
    """Atomically write a snapshot to a date/domain partition."""

    date_partition = snapshot.completed_at.date().isoformat()
    safe_domain = snapshot.domain.replace(":", "_")
    destination = root / date_partition / safe_domain / f"{snapshot.run_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = f"{snapshot.model_dump_json(indent=2)}\n"

    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{snapshot.run_id}.",
        suffix=".tmp",
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return destination
