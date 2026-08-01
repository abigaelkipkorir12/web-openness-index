from html.parser import HTMLParser

from web_openness.models import Confidence, Evidence, Observation
from web_openness.probes.base import ProbeContext, observation

FEED_TYPES = {
    "application/atom+xml",
    "application/feed+json",
    "application/json",
    "application/rss+xml",
}


class MetadataHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.has_json_ld = False
        self.has_open_graph = False
        self.feeds: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "script" and values.get("type", "").lower() == "application/ld+json":
            self.has_json_ld = True
        if tag.lower() == "meta" and values.get("property", "").lower().startswith("og:"):
            self.has_open_graph = True
        if tag.lower() == "link":
            rels = {part.lower() for part in values.get("rel", "").split()}
            media_type = values.get("type", "").lower()
            href = values.get("href", "")
            if "alternate" in rels and media_type in FEED_TYPES and href:
                self.feeds.add(href)


class MetadataProbe:
    name = "homepage_metadata"

    async def collect(self, context: ProbeContext) -> dict[str, Observation]:
        html = context.shared.get("homepage_html")
        evidence_value = context.shared.get("homepage_evidence")
        evidence = [evidence_value] if isinstance(evidence_value, Evidence) else []
        if not isinstance(html, str):
            return {
                key: observation(
                    None,
                    confidence=Confidence.UNKNOWN,
                    score=0.0,
                    method="homepage HTML was unavailable",
                    evidence=evidence,
                )
                for key in (
                    "metadata.json_ld",
                    "metadata.open_graph",
                    "metadata.feeds",
                )
            }

        parser = MetadataHTMLParser()
        parser.feed(html)
        return {
            "metadata.json_ld": observation(
                parser.has_json_ld,
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method="homepage HTML tag detection",
                evidence=evidence,
            ),
            "metadata.open_graph": observation(
                parser.has_open_graph,
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method="homepage HTML tag detection",
                evidence=evidence,
            ),
            "metadata.feeds": observation(
                sorted(parser.feeds),
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method="homepage alternate-link detection",
                evidence=evidence,
            ),
        }
