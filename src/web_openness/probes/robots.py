import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urljoin

from web_openness.models import Confidence, Observation, ProbeError
from web_openness.probes.base import ProbeContext, evidence_from_fetch, observation

KNOWN_AI_AGENTS = {
    "amazonbot",
    "anthropic-ai",
    "bytespider",
    "ccbot",
    "chatgpt-user",
    "claude-web",
    "cohere-ai",
    "google-extended",
    "gptbot",
    "meta-externalagent",
    "perplexitybot",
}


@dataclass(frozen=True, slots=True)
class ParsedRobots:
    user_agents: tuple[str, ...]
    ai_user_agents: tuple[str, ...]
    crawl_delays: dict[str, str]
    sitemaps: tuple[str, ...]


def parse_robots(text: str) -> ParsedRobots:
    user_agents: set[str] = set()
    crawl_delays: dict[str, str] = {}
    sitemaps: set[str] = set()
    current_agents: list[str] = []
    group_has_rules = False

    for raw_line in text.splitlines():
        line = raw_line.split("#", maxsplit=1)[0].strip()
        if not line:
            continue
        key, separator, value = line.partition(":")
        if not separator:
            continue
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            if group_has_rules:
                current_agents = []
                group_has_rules = False
            normalized = value.lower()
            current_agents.append(normalized)
            user_agents.add(normalized)
        elif key == "crawl-delay":
            group_has_rules = True
            for agent in current_agents or ["*"]:
                crawl_delays[agent] = value
        elif key in {"allow", "disallow"}:
            group_has_rules = True
        elif key == "sitemap" and value:
            sitemaps.add(value)

    ai_user_agents = tuple(sorted(user_agents & KNOWN_AI_AGENTS))
    return ParsedRobots(
        user_agents=tuple(sorted(user_agents)),
        ai_user_agents=ai_user_agents,
        crawl_delays=dict(sorted(crawl_delays.items())),
        sitemaps=tuple(sorted(sitemaps)),
    )


class RobotsProbe:
    name = "robots"

    async def collect(self, context: ProbeContext) -> dict[str, Observation]:
        url = urljoin(f"{context.origin}/", "robots.txt")
        result = await context.client.get(url)
        evidence = [evidence_from_fetch(result)]
        status = result.status_code

        if result.error is not None:
            context.shared["robots_allows_followup"] = False
            context.errors.append(ProbeError(probe=self.name, message=result.error))
            return {
                "crawler.robots_exists": observation(
                    None,
                    confidence=Confidence.UNKNOWN,
                    score=0.0,
                    method="robots.txt fetch failed",
                    evidence=evidence,
                )
            }

        if status in {404, 410}:
            context.shared["robots_allows_followup"] = True
            return {
                "crawler.robots_exists": observation(
                    False,
                    confidence=Confidence.CONFIRMED,
                    score=1.0,
                    method="robots.txt returned a not-found status",
                    evidence=evidence,
                ),
                "crawler.robots_status": observation(
                    status,
                    confidence=Confidence.CONFIRMED,
                    score=1.0,
                    method="HTTP status",
                    evidence=evidence,
                ),
            }

        if status != 200:
            context.shared["robots_allows_followup"] = False
            return {
                "crawler.robots_exists": observation(
                    None,
                    confidence=Confidence.UNKNOWN,
                    score=0.2,
                    method="robots.txt returned an inconclusive status",
                    evidence=evidence,
                ),
                "crawler.robots_status": observation(
                    status,
                    confidence=Confidence.CONFIRMED,
                    score=1.0,
                    method="HTTP status",
                    evidence=evidence,
                ),
            }

        parsed = parse_robots(result.text)
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(url)
        parser.parse(result.text.splitlines())
        homepage_url = urljoin(f"{context.origin}/", "/")
        allows_homepage = parser.can_fetch(context.config.user_agent_token, homepage_url)
        context.shared["robot_parser"] = parser
        context.shared["robots_allows_followup"] = allows_homepage
        context.shared["robots_sitemaps"] = list(parsed.sitemaps)

        return {
            "crawler.robots_exists": observation(
                True,
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method="robots.txt returned HTTP 200",
                evidence=evidence,
            ),
            "crawler.robots_status": observation(
                status,
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method="HTTP status",
                evidence=evidence,
            ),
            "crawler.user_agents": observation(
                list(parsed.user_agents),
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method="robots.txt directive parsing",
                evidence=evidence,
            ),
            "crawler.ai_specific_user_agents": observation(
                list(parsed.ai_user_agents),
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method="robots.txt user-agent matching",
                evidence=evidence,
            ),
            "crawler.crawl_delays": observation(
                parsed.crawl_delays,
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method="robots.txt directive parsing",
                evidence=evidence,
            ),
            "crawler.sitemaps": observation(
                list(parsed.sitemaps),
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method="robots.txt sitemap directives",
                evidence=evidence,
            ),
            "crawler.homepage_policy_allowed": observation(
                allows_homepage,
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method=f"robots.txt evaluation for {context.config.user_agent_token}",
                evidence=evidence,
            ),
        }
