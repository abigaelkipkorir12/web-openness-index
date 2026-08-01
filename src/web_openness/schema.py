from typing import Any

from web_openness.models import SCHEMA_VERSION, DomainSnapshot

SCHEMA_FILENAME = f"domain-snapshot-v{SCHEMA_VERSION}.json"
SCHEMA_ID = (
    "https://raw.githubusercontent.com/shayne-longpre/web-openness-index/"
    f"main/schemas/{SCHEMA_FILENAME}"
)


def domain_snapshot_json_schema() -> dict[str, Any]:
    """Return the canonical JSON Schema for the persisted snapshot contract."""

    schema = DomainSnapshot.model_json_schema()
    schema["$id"] = SCHEMA_ID
    return schema
