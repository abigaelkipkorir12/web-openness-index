import httpx
import pytest

from web_openness.config import ScanConfig
from web_openness.models import Confidence
from web_openness.pipeline import Scanner
from web_openness.probes.robots import RobotsProbe
from web_openness.probes.sitemap import (
    MAX_SITEMAP_XML_BYTES,
    SitemapParseError,
    SitemapProbe,
    parse_sitemap,
)


def _scanner(handler: httpx.MockTransport) -> Scanner:
    return Scanner(
        ScanConfig(request_delay_seconds=0),
        probes=(RobotsProbe(), SitemapProbe()),
        transport=handler,
    )


def test_parse_sitemap_rejects_entity_declarations() -> None:
    with pytest.raises(SitemapParseError, match="declarations are not permitted"):
        parse_sitemap(b'<!DOCTYPE urlset [<!ENTITY x "expanded">]><urlset><url>&x;</url></urlset>')


def test_parse_sitemap_enforces_its_own_byte_limit() -> None:
    body = b"<urlset>" + (b" " * MAX_SITEMAP_XML_BYTES) + b"</urlset>"

    with pytest.raises(SitemapParseError, match="exceeded"):
        parse_sitemap(body)


@pytest.mark.asyncio
async def test_declared_urlset_is_fetched_once_and_counted_without_crawling() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text=(
                    "User-agent: *\nAllow: /\n"
                    "Sitemap: https://example.org/catalog.xml\n"
                    "Sitemap: https://example.org/z-unused.xml\n"
                ),
                request=request,
            )
        if request.url.path == "/catalog.xml":
            return httpx.Response(
                200,
                text=(
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    "<url><loc>https://example.org/one</loc></url>"
                    "<url><loc>https://example.org/two</loc></url>"
                    "</urlset>"
                ),
                request=request,
            )
        raise AssertionError(f"unexpected request: {request.url}")

    snapshot = await _scanner(httpx.MockTransport(handler)).scan("example.org")

    assert requested_paths == ["/robots.txt", "/catalog.xml"]
    assert snapshot.observations["metadata.sitemap_exists"].value is True
    assert snapshot.observations["metadata.sitemap_document_type"].value == "urlset"
    assert snapshot.observations["metadata.sitemap_url_count"].value == 2
    assert snapshot.observations["metadata.sitemap_child_sitemap_count"].value == 0


@pytest.mark.asyncio
async def test_fallback_sitemap_index_counts_children_without_fetching_them() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        if request.url.path == "/sitemap.xml":
            return httpx.Response(
                200,
                text=(
                    "<sitemapindex>"
                    "<sitemap><loc>https://example.org/one.xml</loc></sitemap>"
                    "<sitemap><loc>https://example.org/two.xml</loc></sitemap>"
                    "</sitemapindex>"
                ),
                request=request,
            )
        raise AssertionError(f"unexpected request: {request.url}")

    snapshot = await _scanner(httpx.MockTransport(handler)).scan("example.org")

    assert requested_paths == ["/robots.txt", "/sitemap.xml"]
    assert snapshot.observations["metadata.sitemap_document_type"].value == "sitemapindex"
    assert snapshot.observations["metadata.sitemap_url_count"].value == 0
    assert snapshot.observations["metadata.sitemap_child_sitemap_count"].value == 2


@pytest.mark.asyncio
async def test_sitemap_disallowed_by_path_specific_policy_is_not_fetched() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/robots.txt"
        return httpx.Response(
            200,
            text=(
                "User-agent: *\nDisallow: /private-sitemap.xml\nAllow: /\n"
                "Sitemap: https://example.org/private-sitemap.xml\n"
            ),
            request=request,
        )

    snapshot = await _scanner(httpx.MockTransport(handler)).scan("example.org")

    assert snapshot.request_count == 1
    exists = snapshot.observations["metadata.sitemap_exists"]
    assert exists.value is None
    assert exists.confidence == Confidence.UNKNOWN
    assert snapshot.observations["metadata.sitemap_status"].value is None


@pytest.mark.asyncio
async def test_not_found_is_confirmed_absent_with_unknown_document_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        assert request.url.path == "/sitemap.xml"
        return httpx.Response(404, request=request)

    snapshot = await _scanner(httpx.MockTransport(handler)).scan("example.org")

    exists = snapshot.observations["metadata.sitemap_exists"]
    assert exists.value is False
    assert exists.confidence == Confidence.CONFIRMED
    assert snapshot.observations["metadata.sitemap_status"].value == 404
    assert snapshot.observations["metadata.sitemap_document_type"].value is None
    assert snapshot.observations["metadata.sitemap_url_count"].value is None


@pytest.mark.asyncio
async def test_malformed_xml_does_not_become_false_absence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        assert request.url.path == "/sitemap.xml"
        return httpx.Response(200, text="<urlset><url></urlset>", request=request)

    snapshot = await _scanner(httpx.MockTransport(handler)).scan("example.org")

    exists = snapshot.observations["metadata.sitemap_exists"]
    assert exists.value is None
    assert exists.confidence == Confidence.UNKNOWN
    assert snapshot.observations["metadata.sitemap_status"].value == 200
    assert snapshot.observations["metadata.sitemap_document_type"].value is None
    assert snapshot.errors[0].probe == "sitemap"
    assert snapshot.errors[0].message == "sitemap response was malformed XML"


@pytest.mark.asyncio
async def test_fetch_error_is_unknown_and_recorded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404, request=request)
        raise httpx.ConnectError("connection failed", request=request)

    snapshot = await _scanner(httpx.MockTransport(handler)).scan("example.org")

    exists = snapshot.observations["metadata.sitemap_exists"]
    assert exists.value is None
    assert exists.confidence == Confidence.UNKNOWN
    assert snapshot.observations["metadata.sitemap_status"].value is None
    assert snapshot.errors[0].probe == "sitemap"
    assert "ConnectError" in snapshot.errors[0].message
