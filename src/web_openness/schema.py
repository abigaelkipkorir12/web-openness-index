import json
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


def load_domain_snapshot_json(payload: str) -> DomainSnapshot:
    """Validate the current contract or migrate the retained v0.1 observation outcome."""

    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("snapshot JSON must contain an object")
    if value.get("schema_version") == "0.1.0":
        observations = value.get("observations")
        if not isinstance(observations, dict):
            raise ValueError("legacy snapshot observations must contain an object")
        outcome_by_confidence = {
            "confirmed": "observed",
            "likely": "observed",
            "possible": "observed",
            "no_evidence": "no_evidence",
            "unknown": "error",
        }
        for key, raw_observation in observations.items():
            if not isinstance(raw_observation, dict):
                raise ValueError(f"legacy observation {key!r} must contain an object")
            confidence = raw_observation.get("confidence")
            if not isinstance(confidence, str) or confidence not in outcome_by_confidence:
                raise ValueError(f"legacy observation {key!r} has invalid confidence")
            raw_observation["outcome"] = outcome_by_confidence[confidence]
        value["schema_version"] = SCHEMA_VERSION
    return DomainSnapshot.model_validate(value)
