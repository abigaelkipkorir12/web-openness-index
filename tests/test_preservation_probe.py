import hashlib
from dataclasses import replace
from datetime import UTC, datetime

import httpx
import pytest

from web_openness.archive import ArchiveLookup, ArchivePolicy, WaybackCDXClient
from web_openness.client import SiteClient
from web_openness.config import ScanConfig
from web_openness.models import Confidence, ObservationOutcome
from web_openness.probes.base import ProbeContext
from web_openness.probes.preservation import PreservationProbe


def _context(config: ScanConfig, client: SiteClient) -> ProbeContext:
    return ProbeContext(
        domain="example.org",
        origin="https://example.org",
        config=config,
        client=client,
        shared={"robots_allows_followup": True},
    )


@pytest.mark.asyncio
async def test_preservation_network_work_is_disabled_by_default() -> None:
    class UnexpectedArchiveClient:
        async def lookup(self, _target_url: str) -> ArchiveLookup:
            raise AssertionError("disabled archive client was called")

    config = ScanConfig(request_delay_seconds=0)
    context = _context(config, SiteClient(config))
    context.shared["archive_client"] = UnexpectedArchiveClient()

    values = await PreservationProbe().collect(context)

    assert set(values) == {
        "preservation.archive_coverage",
        "preservation.archive_blocked",
        "preservation.cache_behavior",
    }
    assert all(value.outcome == ObservationOutcome.SKIPPED for value in values.values())


@pytest.mark.asyncio
async def test_archive_captures_confirm_coverage_without_retaining_urls() -> None:
    class FakeArchiveClient:
        async def lookup(self, target_url: str) -> ArchiveLookup:
            assert target_url == "https://example.org/"
            return ArchiveLookup(
                endpoint="https://web.archive.org/cdx/search/cdx",
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
                status_code=200,
                capture_timestamps=("20200102030405", "20250102030405"),
            )

    config = ScanConfig(
        request_delay_seconds=0,
        archive_policy=ArchivePolicy(enabled=True),
    )
    context = _context(config, SiteClient(config))
    context.shared["archive_client"] = FakeArchiveClient()

    values = await PreservationProbe().collect(context)

    assert values["preservation.archive_coverage"].value == {
        "homepage_captured": True,
        "monthly_capture_samples": 2,
        "earliest_sampled_capture": "20200102030405",
        "latest_sampled_capture": "20250102030405",
        "sample_capped": False,
    }
    assert values["preservation.archive_blocked"].value is False
    assert values["preservation.archive_blocked"].confidence == Confidence.CONFIRMED


@pytest.mark.asyncio
async def test_empty_archive_result_does_not_claim_not_blocked() -> None:
    class EmptyArchiveClient:
        async def lookup(self, _target_url: str) -> ArchiveLookup:
            return ArchiveLookup(
                endpoint="https://web.archive.org/cdx/search/cdx",
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
                status_code=200,
            )

    config = ScanConfig(
        request_delay_seconds=0,
        archive_policy=ArchivePolicy(enabled=True),
    )
    context = _context(config, SiteClient(config))
    context.shared["archive_client"] = EmptyArchiveClient()

    values = await PreservationProbe().collect(context)

    assert values["preservation.archive_coverage"].value["homepage_captured"] is False
    blocked = values["preservation.archive_blocked"]
    assert blocked.value is None
    assert blocked.outcome == ObservationOutcome.NO_EVIDENCE


@pytest.mark.asyncio
async def test_explicit_archive_exclusion_marker_is_likely_blocked() -> None:
    class BlockedArchiveClient:
        async def lookup(self, _target_url: str) -> ArchiveLookup:
            return ArchiveLookup(
                endpoint="https://web.archive.org/cdx/search/cdx",
                observed_at=datetime(2026, 1, 1, tzinfo=UTC),
                status_code=403,
                blocked=True,
            )

    config = ScanConfig(
        request_delay_seconds=0,
        archive_policy=ArchivePolicy(enabled=True),
    )
    context = _context(config, SiteClient(config))
    context.shared["archive_client"] = BlockedArchiveClient()

    values = await PreservationProbe().collect(context)

    assert values["preservation.archive_coverage"].outcome == ObservationOutcome.NO_EVIDENCE
    blocked = values["preservation.archive_blocked"]
    assert blocked.value is True
    assert blocked.confidence == Confidence.LIKELY


@pytest.mark.asyncio
async def test_wayback_client_parses_one_bounded_monthly_query_offline() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=[["timestamp"], ["20240102030405"], ["20230102030405"]],
            request=request,
        )

    policy = ArchivePolicy(enabled=True, max_monthly_captures=2)
    result = await WaybackCDXClient(
        policy,
        user_agent="ResearchCollector/1.0",
        transport=httpx.MockTransport(handler),
    ).lookup("https://example.org/")

    assert len(requests) == 1
    assert requests[0].url.params.get("url") == "https://example.org/"
    assert requests[0].url.params.get_list("filter") == [
        "statuscode:200",
        "mimetype:text/html",
    ]
    assert requests[0].url.params.get("collapse") == "timestamp:6"
    assert result.capture_timestamps == ("20230102030405", "20240102030405")
    assert result.sample_capped is True
    assert result.error is None


@pytest.mark.asyncio
async def test_wayback_client_requires_explicit_exclusion_text_for_blocked() -> None:
    responses = iter(
        (
            (403, "request forbidden"),
            (403, "Blocked Site Error: this URL has been excluded"),
        )
    )

    def handler(request: httpx.Request) -> httpx.Response:
        status, text = next(responses)
        return httpx.Response(status, text=text, request=request)

    client = WaybackCDXClient(
        ArchivePolicy(enabled=True),
        user_agent="ResearchCollector/1.0",
        transport=httpx.MockTransport(handler),
    )
    ordinary_forbidden = await client.lookup("https://example.org/")
    explicit_exclusion = await client.lookup("https://example.org/")

    assert ordinary_forbidden.blocked is False
    assert explicit_exclusion.blocked is True


@pytest.mark.asyncio
async def test_cache_validation_uses_one_etag_request_and_stores_no_validator() -> None:
    calls = 0
    etag = '"private-validator-value"'

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, headers={"etag": etag}, text="stable", request=request)
        assert request.headers["if-none-match"] == etag
        return httpx.Response(304, request=request)

    config = ScanConfig(request_delay_seconds=0, cache_validation_enabled=True)
    async with SiteClient(config, transport=httpx.MockTransport(handler)) as client:
        homepage = await client.get("https://example.org/")
        context = _context(config, client)
        context.shared["homepage_response"] = homepage
        values = await PreservationProbe().collect(context)

    cache = values["preservation.cache_behavior"]
    assert calls == 2
    assert cache.value == {
        "validator": "etag",
        "conditional_status": 304,
        "result": "not_modified",
        "content_unchanged": True,
    }
    assert etag not in repr(cache)


@pytest.mark.asyncio
async def test_cache_validation_skips_repeat_request_without_validator() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, text="stable", request=request)

    config = ScanConfig(request_delay_seconds=0, cache_validation_enabled=True)
    async with SiteClient(config, transport=httpx.MockTransport(handler)) as client:
        homepage = await client.get("https://example.org/")
        context = _context(config, client)
        context.shared["homepage_response"] = homepage
        values = await PreservationProbe().collect(context)

    assert calls == 1
    assert values["preservation.cache_behavior"].outcome == ObservationOutcome.NO_EVIDENCE


@pytest.mark.asyncio
async def test_full_conditional_response_compares_bounded_content_digests() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        headers = {"last-modified": "Wed, 21 Oct 2015 07:28:00 GMT"}
        return httpx.Response(200, headers=headers, text="stable", request=request)

    config = ScanConfig(request_delay_seconds=0, cache_validation_enabled=True)
    async with SiteClient(config, transport=httpx.MockTransport(handler)) as client:
        homepage = await client.get("https://example.org/")
        assert homepage.evidence.content_sha256 == hashlib.sha256(b"stable").hexdigest()
        context = _context(config, client)
        context.shared["homepage_response"] = homepage
        values = await PreservationProbe().collect(context)

    assert calls == 2
    assert values["preservation.cache_behavior"].value["result"] == ("full_response_unchanged")


@pytest.mark.asyncio
async def test_cache_validation_uses_the_final_canonical_homepage_url() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "example.org":
            return httpx.Response(
                301,
                headers={"location": "https://www.example.org/"},
                request=request,
            )
        if "if-none-match" in request.headers:
            return httpx.Response(304, request=request)
        return httpx.Response(200, headers={"etag": '"v1"'}, text="stable", request=request)

    config = ScanConfig(request_delay_seconds=0, cache_validation_enabled=True)
    async with SiteClient(config, transport=httpx.MockTransport(handler)) as client:
        homepage = await client.get("https://example.org/")
        context = _context(config, client)
        context.shared["homepage_response"] = homepage
        values = await PreservationProbe().collect(context)

    assert [request.url.host for request in requests] == [
        "example.org",
        "www.example.org",
        "www.example.org",
    ]
    assert values["preservation.cache_behavior"].value["result"] == "not_modified"


@pytest.mark.asyncio
async def test_truncated_baseline_is_not_claimed_unchanged() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"etag": '"v1"'}, text="stable", request=request)

    config = ScanConfig(request_delay_seconds=0, cache_validation_enabled=True)
    async with SiteClient(config, transport=httpx.MockTransport(handler)) as client:
        homepage = replace(await client.get("https://example.org/"), truncated=True)
        context = _context(config, client)
        context.shared["homepage_response"] = homepage
        values = await PreservationProbe().collect(context)

    assert homepage.truncated is True
    assert values["preservation.cache_behavior"].value["result"] == ("full_response_not_comparable")
