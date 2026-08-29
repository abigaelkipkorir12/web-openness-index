import csv
from pathlib import Path

import pytest

from web_openness.frame import build_selection_manifest

FIELDS = (
    "domain",
    "source",
    "sector",
    "geography",
    "popularity_band",
    "eligible",
    "exclusion_reason",
)


def _write_frame(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _row(domain: str, *, source: str = "source-a") -> dict[str, str]:
    return {
        "domain": domain,
        "source": source,
        "sector": "news_media",
        "geography": "americas",
        "popularity_band": "head",
        "eligible": "true",
        "exclusion_reason": "",
    }


def test_selection_is_reproducible_and_merges_source_membership(tmp_path: Path) -> None:
    frame = tmp_path / "frame.csv"
    rows = [_row(f"example-{index}.com") for index in range(5)]
    rows.append(_row("www.example-0.com", source="source-b"))
    _write_frame(frame, rows)

    first = build_selection_manifest(
        frame,
        frame_version="pilot-v0.1",
        code_revision="abc123",
        seed="pilot-2026",
        per_stratum=2,
    )
    second = build_selection_manifest(
        frame,
        frame_version="pilot-v0.1",
        code_revision="abc123",
        seed="pilot-2026",
        per_stratum=2,
    )

    assert first.payload == second.payload
    assert len(first.selected_domains) == 2
    assert first.payload["frame_domain_count"] == 5
    domains = first.payload["domains"]
    assert isinstance(domains, list)
    example = next(item for item in domains if item["domain"] == "example-0.com")
    assert example["sources"] == ["source-a", "source-b"]
    assert example["inclusion_probability"] == 0.4

    manifest = tmp_path / "manifest.json"
    targets = tmp_path / "targets.txt"
    first.write(manifest, targets)
    assert targets.read_text(encoding="utf-8").splitlines() == list(first.selected_domains)
    with pytest.raises(FileExistsError, match="selection output already exists"):
        first.write(manifest, targets)


def test_frame_requires_explicit_ineligibility_reason(tmp_path: Path) -> None:
    frame = tmp_path / "frame.csv"
    row = _row("example.com")
    row["eligible"] = "false"
    _write_frame(frame, [row])

    with pytest.raises(ValueError, match="exclusion reason"):
        build_selection_manifest(
            frame,
            frame_version="pilot-v0.1",
            code_revision="abc123",
            seed="pilot",
            per_stratum=1,
        )


def test_example_frame_builds_a_manifest() -> None:
    root = Path(__file__).resolve().parents[1]
    manifest = build_selection_manifest(
        root / "examples/pilot_frame.example.csv",
        frame_version="example-v0.1",
        code_revision="documentation",
        seed="documentation-example",
        per_stratum=1,
    )

    assert manifest.payload["eligible_domain_count"] == 9
    assert manifest.selected_domains
