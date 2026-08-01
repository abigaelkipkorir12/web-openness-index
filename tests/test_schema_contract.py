import json
from pathlib import Path

from pydantic import ValidationError

from web_openness.models import DomainSnapshot
from web_openness.schema import SCHEMA_FILENAME, domain_snapshot_json_schema

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "schemas" / SCHEMA_FILENAME
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "domain_snapshot_v0.1.0.json"


def test_committed_schema_matches_runtime_model() -> None:
    committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert committed == domain_snapshot_json_schema()


def test_versioned_fixture_round_trips() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    snapshot = DomainSnapshot.model_validate(payload)
    assert snapshot.model_dump(mode="json") == payload


def test_unknown_snapshot_fields_are_rejected() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    payload["unversioned_field"] = True
    try:
        DomainSnapshot.model_validate(payload)
    except ValidationError as exc:
        assert "unversioned_field" in str(exc)
    else:
        raise AssertionError("unknown fields must not be silently discarded")
