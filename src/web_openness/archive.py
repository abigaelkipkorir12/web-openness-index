import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from web_openness.safety import validate_public_url

DEFAULT_CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
_BLOCK_MARKERS = (
    "blocked site error",
    "excluded from the wayback machine",
    "this url has been excluded",
)


@dataclass(frozen=True, slots=True)
class ArchivePolicy:
    """Limits for an optional, single-request public archive lookup."""

    enabled: bool = False
    endpoint: str = DEFAULT_CDX_ENDPOINT
    timeout_seconds: float = 15.0
    max_response_bytes: int = 256_000
    max_monthly_captures: int = 120

    def __post_init__(self) -> None:
        parsed = urlsplit(self.endpoint)
        if (
            parsed.scheme != "https"
            or parsed.hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("archive endpoint must be an HTTPS URL without credentials or query")
        if self.timeout_seconds <= 0:
            raise ValueError("archive timeout_seconds must be positive")
        if self.max_response_bytes < 1:
            raise ValueError("archive max_response_bytes must be at least 1")
        if not 1 <= self.max_monthly_captures <= 1_000:
            raise ValueError("archive max_monthly_captures must be between 1 and 1000")


@dataclass(frozen=True, slots=True)
class ArchiveLookup:
    endpoint: str
    observed_at: datetime
    status_code: int | None
    capture_timestamps: tuple[str, ...] = ()
    sample_capped: bool = False
    blocked: bool = False
    truncated: bool = False
    content_sha256: str | None = None
    error: str | None = None


class ArchiveLookupClient(Protocol):
    async def lookup(self, target_url: str) -> ArchiveLookup: ...


class WaybackCDXClient:
    """Bounded client for a monthly-collapsed Wayback CDX homepage query."""

    def __init__(
        self,
        policy: ArchivePolicy,
        *,
        user_agent: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.policy = policy
        self.user_agent = user_agent
        self.transport = transport

    async def lookup(self, target_url: str) -> ArchiveLookup:
        observed_at = datetime.now(UTC)
        try:
            await validate_public_url(
                self.policy.endpoint,
                resolve_dns=not isinstance(self.transport, httpx.MockTransport),
            )
        except (ValueError, TimeoutError) as exc:
            return ArchiveLookup(
                endpoint=self.policy.endpoint,
                observed_at=observed_at,
                status_code=None,
                error=f"{type(exc).__name__}: {exc}",
            )

        params: tuple[tuple[str, str], ...] = (
            ("url", target_url),
            ("output", "json"),
            ("fl", "timestamp"),
            ("filter", "statuscode:200"),
            ("filter", "mimetype:text/html"),
            ("collapse", "timestamp:6"),
            ("limit", str(self.policy.max_monthly_captures)),
        )
        status_code: int | None = None
        body = bytearray()
        truncated = False
        try:
            async with (
                httpx.AsyncClient(
                    headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                    follow_redirects=False,
                    http2=True,
                    timeout=self.policy.timeout_seconds,
                    transport=self.transport,
                    trust_env=False,
                ) as client,
                client.stream("GET", self.policy.endpoint, params=params) as response,
            ):
                status_code = response.status_code
                async for chunk in response.aiter_bytes():
                    remaining = self.policy.max_response_bytes - len(body)
                    if remaining <= 0:
                        truncated = True
                        break
                    body.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        truncated = True
                        break
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            return ArchiveLookup(
                endpoint=self.policy.endpoint,
                observed_at=observed_at,
                status_code=status_code,
                error=f"{type(exc).__name__}: {exc}",
            )

        raw = bytes(body)
        digest = hashlib.sha256(raw).hexdigest() if raw else None
        body_text = raw.decode("utf-8", errors="replace")
        blocked = any(marker in body_text.lower() for marker in _BLOCK_MARKERS)
        if truncated:
            return ArchiveLookup(
                endpoint=self.policy.endpoint,
                observed_at=observed_at,
                status_code=status_code,
                blocked=blocked,
                truncated=True,
                content_sha256=digest,
                error="archive response exceeded the configured byte limit",
            )
        if blocked:
            return ArchiveLookup(
                endpoint=self.policy.endpoint,
                observed_at=observed_at,
                status_code=status_code,
                blocked=True,
                content_sha256=digest,
            )
        if status_code != 200:
            return ArchiveLookup(
                endpoint=self.policy.endpoint,
                observed_at=observed_at,
                status_code=status_code,
                content_sha256=digest,
            )

        try:
            timestamps = _parse_cdx_timestamps(body_text)
        except ValueError as exc:
            return ArchiveLookup(
                endpoint=self.policy.endpoint,
                observed_at=observed_at,
                status_code=status_code,
                content_sha256=digest,
                error=str(exc),
            )
        return ArchiveLookup(
            endpoint=self.policy.endpoint,
            observed_at=observed_at,
            status_code=status_code,
            capture_timestamps=timestamps,
            sample_capped=len(timestamps) >= self.policy.max_monthly_captures,
            content_sha256=digest,
        )


def _parse_cdx_timestamps(body: str) -> tuple[str, ...]:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError("archive returned invalid JSON") from exc
    if not isinstance(payload, list):
        raise ValueError("archive returned an unexpected JSON document")
    if not payload:
        return ()

    header = payload[0]
    if not isinstance(header, list) or "timestamp" not in header:
        raise ValueError("archive response did not include a timestamp column")
    timestamp_index = header.index("timestamp")
    timestamps: list[str] = []
    for row in payload[1:]:
        if not isinstance(row, list) or timestamp_index >= len(row):
            raise ValueError("archive response contained a malformed capture row")
        timestamp = row[timestamp_index]
        if not isinstance(timestamp, str) or not _valid_cdx_timestamp(timestamp):
            raise ValueError("archive response contained an invalid capture timestamp")
        timestamps.append(timestamp)
    return tuple(sorted(set(timestamps)))


def _valid_cdx_timestamp(value: str) -> bool:
    if len(value) != 14 or not value.isascii() or not value.isdigit():
        return False
    try:
        datetime.strptime(value, "%Y%m%d%H%M%S")
    except ValueError:
        return False
    return True
