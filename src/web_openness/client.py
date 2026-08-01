import asyncio
import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from web_openness.config import ScanConfig
from web_openness.models import RequestRecord

STORED_HEADERS = {
    "cache-control",
    "cf-cache-status",
    "content-length",
    "content-type",
    "date",
    "server",
    "via",
    "x-cache",
}


class RequestBudgetExceeded(RuntimeError):
    """Raised before a request would exceed the configured domain budget."""


@dataclass(frozen=True, slots=True)
class FetchResult:
    requested_url: str
    final_url: str | None
    status_code: int | None
    headers: dict[str, str]
    body: bytes
    truncated: bool
    error: str | None
    evidence: RequestRecord

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class SiteClient:
    """An async HTTP client that applies scan policy to every request."""

    def __init__(
        self,
        config: ScanConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self.transport = transport
        self.records: list[RequestRecord] = []
        self._client: httpx.AsyncClient | None = None
        self._last_request_started: float | None = None

    async def __aenter__(self) -> "SiteClient":
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
            },
            follow_redirects=True,
            max_redirects=self.config.max_redirects,
            timeout=self.config.timeout_seconds,
            transport=self.transport,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get(self, url: str) -> FetchResult:
        if self._client is None:
            raise RuntimeError("SiteClient must be used as an async context manager")
        if len(self.records) >= self.config.request_budget:
            raise RequestBudgetExceeded(f"request budget of {self.config.request_budget} exhausted")

        await self._apply_delay()
        started_at = datetime.now(UTC)
        started_clock = time.monotonic()
        self._last_request_started = started_clock
        status_code: int | None = None
        final_url: str | None = None
        response_headers: dict[str, str] = {}
        body = bytearray()
        truncated = False
        error: str | None = None

        try:
            async with self._client.stream("GET", url) as response:
                status_code = response.status_code
                final_url = str(response.url)
                response_headers = {
                    key.lower(): value
                    for key, value in response.headers.items()
                    if key.lower() in STORED_HEADERS
                }
                async for chunk in response.aiter_bytes():
                    remaining = self.config.max_response_bytes - len(body)
                    if remaining <= 0:
                        truncated = True
                        break
                    body.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        truncated = True
                        break
        except httpx.HTTPError as exc:
            error = f"{type(exc).__name__}: {exc}"

        elapsed_ms = (time.monotonic() - started_clock) * 1000
        content_sha256 = hashlib.sha256(body).hexdigest() if body else None
        record = RequestRecord(
            requested_url=url,
            final_url=final_url,
            started_at=started_at,
            elapsed_ms=elapsed_ms,
            status_code=status_code,
            response_bytes=len(body),
            response_truncated=truncated,
            content_sha256=content_sha256,
            error=error,
        )
        self.records.append(record)
        return FetchResult(
            requested_url=url,
            final_url=final_url,
            status_code=status_code,
            headers=response_headers,
            body=bytes(body),
            truncated=truncated,
            error=error,
            evidence=record,
        )

    async def _apply_delay(self) -> None:
        if self._last_request_started is None:
            return
        elapsed = time.monotonic() - self._last_request_started
        remaining = self.config.request_delay_seconds - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
