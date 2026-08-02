from typing import cast

from web_openness.archive import (
    ArchiveLookup,
    ArchiveLookupClient,
    WaybackCDXClient,
)
from web_openness.client import FetchResult, RequestBudgetExceeded
from web_openness.models import (
    Confidence,
    Evidence,
    Observation,
    ObservationOutcome,
    ProbeError,
)
from web_openness.probes.base import ProbeContext, evidence_from_fetch, observation
from web_openness.probes.robots import policy_allows

PRESERVATION_KEYS = (
    "preservation.archive_coverage",
    "preservation.archive_blocked",
    "preservation.cache_behavior",
)


class PreservationProbe:
    """Optional archive lookup and one-request conditional cache validation."""

    name = "preservation"

    async def collect(self, context: ProbeContext) -> dict[str, Observation]:
        observations = await self._archive_observations(context)
        observations["preservation.cache_behavior"] = await self._cache_observation(context)
        return observations

    async def _archive_observations(
        self,
        context: ProbeContext,
    ) -> dict[str, Observation]:
        policy = context.config.archive_policy
        if not policy.enabled:
            return _unavailable_archive(
                "third-party archive lookup is disabled",
                outcome=ObservationOutcome.SKIPPED,
            )

        injected = context.shared.get("archive_client")
        client: ArchiveLookupClient
        if injected is None:
            client = WaybackCDXClient(policy, user_agent=context.config.user_agent)
        else:
            client = cast(ArchiveLookupClient, injected)

        try:
            result = await client.lookup(f"{context.origin}/")
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            context.errors.append(ProbeError(probe=self.name, message=message))
            return _unavailable_archive("archive lookup failed")
        return _classify_archive_lookup(context, result)

    async def _cache_observation(self, context: ProbeContext) -> Observation:
        if not context.config.cache_validation_enabled:
            return _unavailable_cache(
                "conditional cache validation is disabled",
                outcome=ObservationOutcome.SKIPPED,
            )
        if context.shared.get("robots_allows_followup") is not True:
            return _unavailable_cache(
                "skipped because crawler policy was not affirmatively allowed",
                outcome=ObservationOutcome.SKIPPED,
            )

        homepage = context.shared.get("homepage_response")
        if not isinstance(homepage, FetchResult):
            return _unavailable_cache("homepage response was unavailable")
        baseline_evidence = [evidence_from_fetch(homepage, note="initial homepage response")]
        if homepage.error is not None:
            return _unavailable_cache("homepage fetch failed", evidence=baseline_evidence)
        if homepage.status_code is None or not 200 <= homepage.status_code < 300:
            return observation(
                None,
                confidence=Confidence.NO_EVIDENCE,
                score=0.0,
                method="homepage did not return a successful representation to validate",
                evidence=baseline_evidence,
            )

        target_url = homepage.final_url or homepage.requested_url
        if not policy_allows(context, target_url):
            return _unavailable_cache(
                "conditional validation skipped because the final homepage path was disallowed",
                evidence=baseline_evidence,
                outcome=ObservationOutcome.SKIPPED,
            )

        validator_name: str
        if etag := homepage.headers.get("etag"):
            validator_name = "etag"
            request_headers = {"If-None-Match": etag}
        elif last_modified := homepage.headers.get("last-modified"):
            validator_name = "last-modified"
            request_headers = {"If-Modified-Since": last_modified}
        else:
            return observation(
                None,
                confidence=Confidence.NO_EVIDENCE,
                score=0.0,
                method="homepage supplied neither ETag nor Last-Modified; no repeat request sent",
                evidence=baseline_evidence,
            )

        try:
            result = await context.client.get(target_url, conditional_headers=request_headers)
        except RequestBudgetExceeded:
            return _unavailable_cache(
                "conditional validation skipped because the origin request budget was exhausted",
                evidence=baseline_evidence,
                outcome=ObservationOutcome.SKIPPED,
            )
        evidence = [
            *baseline_evidence,
            evidence_from_fetch(
                result,
                note=f"conditional homepage response using {validator_name}",
            ),
        ]
        if result.error is not None:
            context.errors.append(ProbeError(probe=self.name, message=result.error))
            return _unavailable_cache("conditional homepage request failed", evidence=evidence)
        if len(result.attempts) != 1 or (result.final_url or result.requested_url) != target_url:
            return observation(
                None,
                confidence=Confidence.NO_EVIDENCE,
                score=0.0,
                method="conditional request redirected or retried; result was not classified",
                evidence=evidence,
            )
        if result.status_code == 304:
            return observation(
                {
                    "validator": validator_name,
                    "conditional_status": 304,
                    "result": "not_modified",
                    "content_unchanged": True,
                },
                confidence=Confidence.CONFIRMED,
                score=1.0,
                method="single conditional homepage request",
                evidence=evidence,
            )
        if result.status_code != 200:
            return observation(
                None,
                confidence=Confidence.NO_EVIDENCE,
                score=0.0,
                method="conditional homepage request returned an inconclusive status",
                evidence=evidence,
            )
        if result.truncated:
            message = "conditional homepage response was truncated at the response-size limit"
            context.errors.append(ProbeError(probe=self.name, message=message))
            return _unavailable_cache(message, evidence=evidence)

        baseline_digest = homepage.evidence.content_sha256
        validation_digest = result.evidence.content_sha256
        unchanged = (
            baseline_digest == validation_digest
            if (
                not homepage.truncated
                and baseline_digest is not None
                and validation_digest is not None
            )
            else None
        )
        result_name = {
            True: "full_response_unchanged",
            False: "full_response_changed",
            None: "full_response_not_comparable",
        }[unchanged]
        return observation(
            {
                "validator": validator_name,
                "conditional_status": 200,
                "result": result_name,
                "content_unchanged": unchanged,
            },
            confidence=Confidence.CONFIRMED,
            score=1.0,
            method="single conditional homepage request and bounded content-digest comparison",
            evidence=evidence,
        )


def _classify_archive_lookup(
    context: ProbeContext,
    result: ArchiveLookup,
) -> dict[str, Observation]:
    evidence = [
        Evidence(
            source_url=result.endpoint,
            observed_at=result.observed_at,
            http_status=result.status_code,
            content_sha256=result.content_sha256,
            note="one opt-in, monthly-collapsed public archive index query",
        )
    ]
    if result.error is not None:
        context.errors.append(ProbeError(probe="preservation", message=result.error))
        return _unavailable_archive("archive lookup failed", evidence=evidence)
    if result.blocked:
        return {
            "preservation.archive_coverage": observation(
                None,
                confidence=Confidence.NO_EVIDENCE,
                score=0.0,
                method="archive exclusion response did not expose coverage",
                evidence=evidence,
            ),
            "preservation.archive_blocked": observation(
                True,
                confidence=Confidence.LIKELY,
                score=0.9,
                method="explicit exclusion marker in the public archive response",
                evidence=evidence,
            ),
        }
    if result.status_code != 200:
        return {
            key: observation(
                None,
                confidence=Confidence.NO_EVIDENCE,
                score=0.0,
                method="archive endpoint returned an inconclusive status",
                evidence=evidence,
            )
            for key in ("preservation.archive_coverage", "preservation.archive_blocked")
        }

    captures = result.capture_timestamps
    coverage = {
        "homepage_captured": bool(captures),
        "monthly_capture_samples": len(captures),
        "earliest_sampled_capture": captures[0] if captures else None,
        "latest_sampled_capture": captures[-1] if captures else None,
        "sample_capped": result.sample_capped,
    }
    blocked = (
        observation(
            False,
            confidence=Confidence.CONFIRMED,
            score=1.0,
            method="public archive returned at least one homepage capture",
            evidence=evidence,
        )
        if captures
        else observation(
            None,
            confidence=Confidence.NO_EVIDENCE,
            score=0.0,
            method="an empty archive result does not distinguish absence from blocking",
            evidence=evidence,
        )
    )
    return {
        "preservation.archive_coverage": observation(
            coverage,
            confidence=Confidence.CONFIRMED,
            score=1.0,
            method="monthly-collapsed homepage captures returned by the public archive index",
            evidence=evidence,
        ),
        "preservation.archive_blocked": blocked,
    }


def _unavailable_archive(
    method: str,
    *,
    evidence: list[Evidence] | None = None,
    outcome: ObservationOutcome = ObservationOutcome.ERROR,
) -> dict[str, Observation]:
    return {
        key: observation(
            None,
            confidence=Confidence.UNKNOWN,
            score=0.0,
            method=method,
            evidence=evidence,
            outcome=outcome,
        )
        for key in ("preservation.archive_coverage", "preservation.archive_blocked")
    }


def _unavailable_cache(
    method: str,
    *,
    evidence: list[Evidence] | None = None,
    outcome: ObservationOutcome = ObservationOutcome.ERROR,
) -> Observation:
    return observation(
        None,
        confidence=Confidence.UNKNOWN,
        score=0.0,
        method=method,
        evidence=evidence,
        outcome=outcome,
    )
