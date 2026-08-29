from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from protego import Protego

from web_openness.client import FetchResult, SiteClient
from web_openness.config import ScanConfig
from web_openness.models import Confidence, Evidence, ObservationOutcome, RequestRecord
from web_openness.probes.base import ProbeContext
from web_openness.probes.policy_signals import (
    PolicySignalsProbe,
    analyze_public_text,
    discover_candidates,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _homepage_result(html: str, *, truncated: bool = False) -> FetchResult:
    record = RequestRecord(
        requested_url="https://example.org/",
        final_url="https://www.example.org/",
        started_at=datetime.now(UTC),
        elapsed_ms=1,
        status_code=200,
        response_bytes=len(html),
        response_truncated=truncated,
    )
    return FetchResult(
        requested_url=record.requested_url,
        final_url=record.final_url,
        status_code=record.status_code,
        http_version="HTTP/2",
        headers={"content-type": "text/html"},
        body=html.encode(),
        truncated=truncated,
        error=None,
        evidence=record,
    )


def _context(config: ScanConfig, client: SiteClient, html: str) -> ProbeContext:
    result = _homepage_result(html)
    context = ProbeContext(
        domain="example.org",
        origin="https://example.org",
        config=config,
        client=client,
    )
    context.shared.update(
        {
            "robots_allows_followup": True,
            "homepage_html": html,
            "homepage_response": result,
            "homepage_evidence": Evidence(
                source_url="https://www.example.org/",
                observed_at=result.evidence.started_at,
                http_status=200,
            ),
        }
    )
    return context


def test_text_analysis_requires_explicit_declarations() -> None:
    findings = analyze_public_text(
        "Researchers discuss scraping, AI training, registration, rate limits, and API prices. "
        "You may not criticize our AI training policy. We handled 100 requests per day. "
        "API access is not free.",
        "https://example.org/article",
    )

    assert not findings.scraping
    assert not findings.ai
    assert not findings.registration_required
    assert not findings.registration_not_required
    assert not findings.metering
    assert not findings.api_pricing


def test_candidate_discovery_is_same_site_and_does_not_treat_signup_as_evidence() -> None:
    filler = "".join(f'<a href="/article/{index}">Article</a>' for index in range(110))
    candidates = discover_candidates(
        f"""
        {filler}
        <a href="/terms">Terms</a>
        <a href="/pricing">Pricing</a>
        <a href="/signup">Create account</a>
        <a href="https://other.example/terms">External terms</a>
        """,
        "https://www.example.org/",
    )

    assert [(item.url, item.scope) for item in candidates] == [
        (
            "https://www.example.org/terms",
            (
                "legal.scraping_restrictions",
                "legal.ai_restrictions",
                "economic.registration_required",
            ),
        ),
        (
            "https://www.example.org/pricing",
            (
                "economic.registration_required",
                "economic.metering",
                "economic.api_pricing",
            ),
        ),
    ]


@pytest.mark.asyncio
async def test_fetches_two_bounded_documents_and_collects_explicit_signals() -> None:
    terms = (FIXTURES / "policy_terms.html").read_text()
    pricing = (FIXTURES / "api_pricing.html").read_text()
    homepage = '<a href="/terms">Terms</a><a href="/api-pricing">API pricing</a>'
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        body = terms if request.url.path == "/terms" else pricing
        return httpx.Response(200, headers={"content-type": "text/html"}, text=body)

    config = ScanConfig(request_delay_seconds=0, request_budget=4, politeness_db_path=None)
    async with SiteClient(config, transport=httpx.MockTransport(handler)) as client:
        values = await PolicySignalsProbe().collect(_context(config, client, homepage))

    assert requested == ["/terms", "/api-pricing"]
    assert values["legal.scraping_restrictions"].confidence == Confidence.CONFIRMED
    assert values["legal.ai_restrictions"].confidence == Confidence.CONFIRMED
    assert values["economic.registration_required"].value is True
    assert values["economic.metering"].value["declarations"][0]["detail"] == (
        "includes 1,000 API calls per month"
    )
    pricing_rules = {item["rule"] for item in values["economic.api_pricing"].value["declarations"]}
    assert pricing_rules == {"published_api_price"}
    assert values["economic.api_pricing"].evidence[0].source_url.endswith("/api-pricing")


@pytest.mark.asyncio
async def test_conflicting_registration_declarations_abstain() -> None:
    homepage = "No registration is required. You must create an account to use the API."
    config = ScanConfig(request_delay_seconds=0, politeness_db_path=None)
    transport = httpx.MockTransport(lambda _: httpx.Response(500))
    async with SiteClient(config, transport=transport) as client:
        values = await PolicySignalsProbe().collect(_context(config, client, homepage))

    finding = values["economic.registration_required"]
    assert finding.value is None
    assert finding.confidence == Confidence.UNKNOWN
    assert finding.outcome == ObservationOutcome.ERROR
    assert not client.records


@pytest.mark.asyncio
async def test_robots_blocked_candidate_is_skipped_without_a_request() -> None:
    homepage = '<a href="/terms">Terms</a>'
    config = ScanConfig(request_delay_seconds=0, politeness_db_path=None)
    transport = httpx.MockTransport(lambda _: httpx.Response(500))
    async with SiteClient(config, transport=transport) as client:
        context = _context(config, client, homepage)
        context.shared["robots_policy"] = Protego.parse(
            "User-agent: WebOpennessObservatory\nDisallow: /terms\n"
        )
        values = await PolicySignalsProbe().collect(context)

    assert values["legal.scraping_restrictions"].outcome == ObservationOutcome.SKIPPED
    assert values["legal.ai_restrictions"].outcome == ObservationOutcome.SKIPPED
    assert values["economic.registration_required"].outcome == ObservationOutcome.SKIPPED
    assert values["economic.metering"].outcome == ObservationOutcome.NO_EVIDENCE
    assert not client.records


@pytest.mark.asyncio
async def test_request_reserve_skips_followup_instead_of_exhausting_budget() -> None:
    homepage = '<a href="/pricing">Pricing</a>'
    config = ScanConfig(request_delay_seconds=0, request_budget=1, politeness_db_path=None)
    transport = httpx.MockTransport(lambda _: httpx.Response(500))
    async with SiteClient(config, transport=transport) as client:
        values = await PolicySignalsProbe().collect(_context(config, client, homepage))

    assert values["economic.api_pricing"].outcome == ObservationOutcome.SKIPPED
    assert not client.records


@pytest.mark.asyncio
async def test_positive_finding_survives_truncated_source() -> None:
    homepage = "You may not scrape this site."
    config = ScanConfig(request_delay_seconds=0, politeness_db_path=None)
    transport = httpx.MockTransport(lambda _: httpx.Response(500))
    async with SiteClient(config, transport=transport) as client:
        context = _context(config, client, homepage)
        context.shared["homepage_response"] = _homepage_result(homepage, truncated=True)
        values = await PolicySignalsProbe().collect(context)

    assert values["legal.scraping_restrictions"].outcome == ObservationOutcome.OBSERVED
    assert values["legal.ai_restrictions"].outcome == ObservationOutcome.ERROR
