import urllib.robotparser
from urllib.parse import urljoin

from web_openness.models import Confidence, Observation, ProbeError
from web_openness.probes.base import ProbeContext, evidence_from_fetch, observation


class WellKnownProbe:
    name = "well_known"

    async def collect(self, context: ProbeContext) -> dict[str, Observation]:
        url = urljoin(f"{context.origin}/", "llms.txt")
        parser_value = context.shared.get("robot_parser")
        if isinstance(parser_value, urllib.robotparser.RobotFileParser):
            allowed = parser_value.can_fetch(context.config.user_agent_token, url)
        else:
            allowed = context.shared.get("robots_allows_followup") is True

        if not allowed:
            return {
                "metadata.llms_txt_exists": observation(
                    None,
                    confidence=Confidence.UNKNOWN,
                    score=0.0,
                    method="skipped because crawler policy was not affirmatively allowed",
                )
            }

        result = await context.client.get(url)
        evidence = [evidence_from_fetch(result)]
        if result.error is not None:
            context.errors.append(ProbeError(probe=self.name, message=result.error))
            return {
                "metadata.llms_txt_exists": observation(
                    None,
                    confidence=Confidence.UNKNOWN,
                    score=0.0,
                    method="llms.txt fetch failed",
                    evidence=evidence,
                )
            }

        exists = result.status_code == 200 and bool(result.body.strip())
        return {
            "metadata.llms_txt_exists": observation(
                exists,
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method="public llms.txt HTTP response",
                evidence=evidence,
            ),
            "metadata.llms_txt_status": observation(
                result.status_code,
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method="HTTP status",
                evidence=evidence,
            ),
        }
