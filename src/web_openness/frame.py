import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from web_openness.domains import canonical_hostname, registrable_domain

FRAME_SCHEMA_VERSION = "0.1.0"

SECTORS = frozenset(
    {
        "academia_research",
        "commerce",
        "forums_communities",
        "general_other",
        "government_civic",
        "news_media",
    }
)
GEOGRAPHIES = frozenset({"africa", "americas", "asia", "europe", "global_or_unassigned", "oceania"})
POPULARITY_BANDS = frozenset({"head", "middle", "long_tail"})


@dataclass(frozen=True, slots=True)
class FrameRecord:
    domain: str
    sources: tuple[str, ...]
    sector: str
    geography: str
    popularity_band: str
    eligible: bool
    exclusion_reason: str | None = None

    @property
    def stratum(self) -> tuple[str, str, str]:
        return self.sector, self.geography, self.popularity_band


@dataclass(frozen=True, slots=True)
class SelectionManifest:
    payload: dict[str, object]

    @property
    def selected_domains(self) -> tuple[str, ...]:
        domains = self.payload["domains"]
        if not isinstance(domains, list):
            raise ValueError("manifest domains must be a list")
        return tuple(
            str(item["domain"])
            for item in domains
            if isinstance(item, dict) and item.get("selected") is True
        )

    def write(self, manifest_path: Path, targets_path: Path) -> None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        targets_path.parent.mkdir(parents=True, exist_ok=True)
        existing = [path for path in (manifest_path, targets_path) if path.exists()]
        if existing:
            names = ", ".join(str(path) for path in existing)
            raise FileExistsError(f"selection output already exists: {names}")
        with manifest_path.open("x", encoding="utf-8") as handle:
            handle.write(f"{json.dumps(self.payload, indent=2, sort_keys=True)}\n")
        with targets_path.open("x", encoding="utf-8") as handle:
            handle.write("".join(f"{domain}\n" for domain in self.selected_domains))


def build_selection_manifest(
    frame_path: Path,
    *,
    frame_version: str,
    code_revision: str,
    seed: str,
    per_stratum: int,
) -> SelectionManifest:
    if not frame_version.strip():
        raise ValueError("frame_version must not be empty")
    if not code_revision.strip():
        raise ValueError("code_revision must not be empty")
    if not seed:
        raise ValueError("seed must not be empty")
    if per_stratum < 1:
        raise ValueError("per_stratum must be at least one")

    frame_bytes = frame_path.read_bytes()
    records = _load_frame(frame_path)
    grouped: dict[tuple[str, str, str], list[FrameRecord]] = defaultdict(list)
    for record in records:
        if record.eligible:
            grouped[record.stratum].append(record)

    selected: set[str] = set()
    order_by_domain: dict[str, int] = {}
    stratum_size_by_domain: dict[str, int] = {}
    strata: list[dict[str, object]] = []
    for stratum in sorted(grouped):
        ordered = sorted(
            grouped[stratum],
            key=lambda record: (_selection_key(seed, record.domain), record.domain),
        )
        chosen = ordered[:per_stratum]
        selected.update(record.domain for record in chosen)
        for order, record in enumerate(ordered, start=1):
            order_by_domain[record.domain] = order
            stratum_size_by_domain[record.domain] = len(ordered)
        strata.append(
            {
                "sector": stratum[0],
                "geography": stratum[1],
                "popularity_band": stratum[2],
                "frame_size": len(ordered),
                "selected_size": len(chosen),
            }
        )

    domains: list[dict[str, object]] = []
    for record in records:
        stratum_size = stratum_size_by_domain.get(record.domain)
        selected_size = min(per_stratum, stratum_size) if stratum_size is not None else 0
        domains.append(
            {
                "domain": record.domain,
                "sources": list(record.sources),
                "sector": record.sector,
                "geography": record.geography,
                "popularity_band": record.popularity_band,
                "eligible": record.eligible,
                "exclusion_reason": record.exclusion_reason,
                "random_order": order_by_domain.get(record.domain),
                "stratum_size": stratum_size,
                "selected": record.domain in selected,
                "inclusion_probability": (
                    selected_size / stratum_size if stratum_size is not None else 0.0
                ),
            }
        )

    payload: dict[str, object] = {
        "schema_version": FRAME_SCHEMA_VERSION,
        "frame_version": frame_version,
        "code_revision": code_revision,
        "seed": seed,
        "per_stratum": per_stratum,
        "frame_sha256": hashlib.sha256(frame_bytes).hexdigest(),
        "frame_domain_count": len(records),
        "eligible_domain_count": sum(record.eligible for record in records),
        "selected_domain_count": len(selected),
        "sources": sorted({source for record in records for source in record.sources}),
        "strata": strata,
        "domains": domains,
    }
    return SelectionManifest(payload)


def _load_frame(path: Path) -> tuple[FrameRecord, ...]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = {
            "domain",
            "source",
            "sector",
            "geography",
            "popularity_band",
            "eligible",
            "exclusion_reason",
        }
        if reader.fieldnames is None or set(reader.fieldnames) != expected:
            raise ValueError(f"frame columns must be exactly: {', '.join(sorted(expected))}")
        raw_rows = list(reader)

    merged: dict[str, FrameRecord] = {}
    for line_number, row in enumerate(raw_rows, start=2):
        record = _parse_row(row, line_number)
        prior = merged.get(record.domain)
        if prior is None:
            merged[record.domain] = record
            continue
        comparable = (
            prior.sector,
            prior.geography,
            prior.popularity_band,
            prior.eligible,
            prior.exclusion_reason,
        )
        current = (
            record.sector,
            record.geography,
            record.popularity_band,
            record.eligible,
            record.exclusion_reason,
        )
        if comparable != current:
            raise ValueError(f"conflicting frame rows for {record.domain}")
        merged[record.domain] = FrameRecord(
            domain=record.domain,
            sources=tuple(sorted(set(prior.sources + record.sources))),
            sector=record.sector,
            geography=record.geography,
            popularity_band=record.popularity_band,
            eligible=record.eligible,
            exclusion_reason=record.exclusion_reason,
        )
    return tuple(merged[domain] for domain in sorted(merged))


def _parse_row(row: dict[str, str], line_number: int) -> FrameRecord:
    raw_domain = row["domain"].strip()
    try:
        domain = registrable_domain(canonical_hostname(raw_domain))
    except ValueError as exc:
        raise ValueError(f"invalid frame domain on line {line_number}: {exc}") from exc
    source = row["source"].strip()
    if not source:
        raise ValueError(f"frame source is empty on line {line_number}")
    sector = _category(row["sector"], SECTORS, "sector", line_number)
    geography = _category(row["geography"], GEOGRAPHIES, "geography", line_number)
    popularity_band = _category(
        row["popularity_band"], POPULARITY_BANDS, "popularity_band", line_number
    )
    eligible_value = row["eligible"].strip().lower()
    if eligible_value not in {"true", "false"}:
        raise ValueError(f"eligible must be true or false on line {line_number}")
    eligible = eligible_value == "true"
    exclusion_reason = row["exclusion_reason"].strip() or None
    if eligible and exclusion_reason is not None:
        raise ValueError(f"eligible row has an exclusion reason on line {line_number}")
    if not eligible and exclusion_reason is None:
        raise ValueError(f"ineligible row needs an exclusion reason on line {line_number}")
    return FrameRecord(
        domain=domain,
        sources=(source,),
        sector=sector,
        geography=geography,
        popularity_band=popularity_band,
        eligible=eligible,
        exclusion_reason=exclusion_reason,
    )


def _category(value: str, allowed: frozenset[str], name: str, line_number: int) -> str:
    normalized = value.strip().lower()
    if normalized not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"invalid {name} on line {line_number}; expected one of: {choices}")
    return normalized


def _selection_key(seed: str, domain: str) -> bytes:
    return hashlib.sha256(f"{seed}\0{domain}".encode()).digest()
