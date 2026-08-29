#!/usr/bin/env python3
import argparse
import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlsplit

from web_openness.governance import CeaseList

_PROBING_REQUIRED_FIELDS = {
    "Canonical",
    "Contact",
    "Description",
    "Expires",
    "Preferred-Languages",
}
_COMPLAINT_FIELDS = {"domain", "scope", "received_at", "status", "reference"}
_PLACEHOLDERS = ("example.org", "REPLACE_", "000.000.000.000")


def check_readiness(
    *,
    site_dir: Path,
    cease_list_path: Path,
    state_path: Path,
    complaint_log_path: Path,
    now: datetime | None = None,
) -> list[str]:
    """Return readiness failures without changing operational state."""

    checked_at = now or datetime.now(UTC)
    failures: list[str] = []
    index_text = _read_required(site_dir / "index.html", "scanner page", failures)
    probing_text = _read_required(
        site_dir / ".well-known" / "probing.txt",
        "probing.txt",
        failures,
    )

    if index_text is not None:
        _check_scanner_page(index_text, failures)
    fields: dict[str, str] = {}
    if probing_text is not None:
        fields = _check_probing_txt(probing_text, checked_at, failures)
    contact = fields.get("Contact")
    if index_text is not None and contact is not None and contact not in index_text:
        failures.append("scanner page does not publish the probing.txt Contact value")

    try:
        CeaseList.load(cease_list_path)
    except (OSError, ValueError) as exc:
        failures.append(f"cease list is unavailable or invalid: {exc}")

    _check_runner_control(state_path, failures)
    _check_complaint_log(complaint_log_path, failures)
    return failures


def _read_required(path: Path, label: str, failures: list[str]) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        failures.append(f"{label} is unavailable as UTF-8 at {path}: {exc}")
        return None


def _check_scanner_page(text: str, failures: list[str]) -> None:
    lowered = text.lower()
    for phrase in ("user-agent", "source address", "opt-out", "robots.txt"):
        if phrase not in lowered:
            failures.append(f"scanner page is missing required disclosure: {phrase}")
    _check_placeholders(text, "scanner page", failures)


def _check_probing_txt(
    text: str,
    now: datetime,
    failures: list[str],
) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition(":")
        if not separator or not name or not value.strip():
            failures.append(f"probing.txt line {line_number} is not a Field: value pair")
            continue
        if name in fields:
            failures.append(f"probing.txt repeats field {name}")
            continue
        fields[name] = value.strip()

    missing = sorted(_PROBING_REQUIRED_FIELDS - fields.keys())
    if missing:
        failures.append(f"probing.txt is missing fields: {', '.join(missing)}")
    _check_placeholders(text, "probing.txt", failures)

    canonical = fields.get("Canonical")
    if canonical is not None:
        parsed = urlsplit(canonical)
        if (
            parsed.scheme != "https"
            or parsed.hostname is None
            or parsed.path != ("/.well-known/probing.txt")
        ):
            failures.append("probing.txt Canonical must be its public HTTPS well-known URL")
    contact = fields.get("Contact")
    if contact is not None:
        parsed = urlsplit(contact)
        if not (
            (parsed.scheme == "mailto" and bool(parsed.path))
            or (parsed.scheme == "https" and parsed.hostname is not None)
        ):
            failures.append("probing.txt Contact must be a mailto or HTTPS URI")
    expires = fields.get("Expires")
    if expires is not None:
        try:
            expiration = _parse_timestamp(expires)
        except ValueError:
            failures.append("probing.txt Expires must be an RFC 3339 timestamp")
        else:
            if expiration <= now:
                failures.append("probing.txt Expires is not in the future")
            if expiration > now + timedelta(days=365):
                failures.append("probing.txt Expires is more than one year in the future")
    return fields


def _check_placeholders(text: str, label: str, failures: list[str]) -> None:
    if any(placeholder in text for placeholder in _PLACEHOLDERS):
        failures.append(f"{label} still contains deployment placeholders")


def _check_runner_control(path: Path, failures: list[str]) -> None:
    if not path.is_file():
        failures.append(f"runner state database does not exist: {path}")
        return
    uri = f"file:{quote(str(path.resolve()))}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            row = connection.execute(
                "SELECT global_stop_requested FROM runner_control WHERE singleton = 1"
            ).fetchone()
    except sqlite3.Error as exc:
        failures.append(f"runner global-stop control is unavailable: {exc}")
        return
    if row is None or row[0] not in {0, 1}:
        failures.append("runner global-stop control has an invalid state")
    elif bool(row[0]):
        failures.append("runner global stop is active; review the incident before collection")


def _check_complaint_log(path: Path, failures: list[str]) -> None:
    text = _read_required(path, "complaint log", failures)
    if text is None:
        return
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError:
            failures.append(f"complaint log line {line_number} is not valid JSON")
            continue
        if not isinstance(value, dict):
            failures.append(f"complaint log line {line_number} is not a JSON object")
            continue
        missing = sorted(_COMPLAINT_FIELDS - value.keys())
        if missing:
            failures.append(
                f"complaint log line {line_number} is missing fields: {', '.join(missing)}"
            )


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone is required")
    return parsed.astimezone(UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check local collector deployment readiness")
    parser.add_argument("--site-dir", type=Path, required=True)
    parser.add_argument("--cease-list", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--complaint-log", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    failures = check_readiness(
        site_dir=args.site_dir,
        cease_list_path=args.cease_list,
        state_path=args.state,
        complaint_log_path=args.complaint_log,
    )
    print(json.dumps({"ready": not failures, "failures": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
