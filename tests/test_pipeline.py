from pathlib import Path

import httpx
import pytest

from web_openness.config import ScanConfig
from web_openness.models import Confidence
from web_openness.pipeline import Scanner, normalize_target
from web_openness.probes import (
    HomepageProbe,
    MetadataProbe,
    RobotsProbe,
    SitemapProbe,
    WellKnownProbe,
)
from web_openness.storage import write_snapshot

OFFLINE_HTTP_PROBES = (
    RobotsProbe(),
    SitemapProbe(),
    HomepageProbe(),
    MetadataProbe(),
    WellKnownProbe(),
)


def test_normalize_target() -> None:
    assert normalize_target("Example.ORG/path") == ("example.org", "https://example.org")
    assert normalize_target("http://example.org:8080") == (
        "example.org",
        "http://example.org:8080",
    )


@pytest.mark.asyncio
async def test_scan_collects_evidence_without_live_network(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text=(
                    "User-agent: *\nAllow: /\n"
                    "User-agent: GPTBot\nDisallow: /\n"
                    "Sitemap: https://example.org/sitemap.xml\n"
                ),
                request=request,
            )
        if request.url.path == "/llms.txt":
            return httpx.Response(200, text="# Example", request=request)
        if request.url.path == "/sitemap.xml":
            return httpx.Response(
                200,
                text=(
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    "<url><loc>https://example.org/one</loc></url>"
                    "</urlset>"
                ),
                request=request,
            )
        if request.url.path == "/":
            return httpx.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                text=(
                    '<meta property="og:title" content="Example">'
                    '<script type="application/ld+json">{}</script>'
                    '<link rel="alternate" type="application/rss+xml" href="/feed.xml">'
                ),
                request=request,
            )
        raise AssertionError(f"unexpected request: {request.url}")

    scanner = Scanner(
        ScanConfig(request_delay_seconds=0),
        probes=OFFLINE_HTTP_PROBES,
        transport=httpx.MockTransport(handler),
    )
    snapshot = await scanner.scan("example.org")

    assert snapshot.domain == "example.org"
    assert snapshot.request_count == 4
    assert snapshot.errors == []
    assert snapshot.observations["crawler.robots_exists"].value is True
    assert snapshot.observations["crawler.ai_specific_user_agents"].value == ["gptbot"]
    assert snapshot.observations["human.homepage_accessible"].value is True
    assert snapshot.observations["metadata.sitemap_exists"].value is True
    assert snapshot.observations["metadata.sitemap_url_count"].value == 1
    assert snapshot.observations["metadata.json_ld"].value is True
    assert snapshot.observations["metadata.open_graph"].value is True
    assert snapshot.observations["metadata.feeds"].value == ["/feed.xml"]
    assert snapshot.observations["metadata.llms_txt_exists"].value is True

    path = write_snapshot(snapshot, tmp_path)
    assert path.exists()
    assert f'"run_id": "{snapshot.run_id}"' in path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_robots_disallow_skips_all_followup_requests() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/robots.txt"
        return httpx.Response(200, text="User-agent: *\nDisallow: /\n", request=request)

    scanner = Scanner(
        ScanConfig(request_delay_seconds=0),
        probes=OFFLINE_HTTP_PROBES,
        transport=httpx.MockTransport(handler),
    )
    snapshot = await scanner.scan("example.org")

    assert snapshot.request_count == 1
    assert snapshot.observations["crawler.homepage_policy_allowed"].value is False
    homepage = snapshot.observations["human.homepage_accessible"]
    assert homepage.value is None
    assert homepage.confidence == Confidence.UNKNOWN
    assert snapshot.observations["metadata.llms_txt_exists"].value is None


@pytest.mark.asyncio
async def test_inconclusive_robots_status_fails_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/robots.txt"
        return httpx.Response(403, request=request)

    scanner = Scanner(
        ScanConfig(request_delay_seconds=0),
        probes=OFFLINE_HTTP_PROBES,
        transport=httpx.MockTransport(handler),
    )
    snapshot = await scanner.scan("example.org")

    assert snapshot.request_count == 1
    assert snapshot.observations["crawler.robots_exists"].value is None
    assert snapshot.observations["human.homepage_accessible"].value is None
