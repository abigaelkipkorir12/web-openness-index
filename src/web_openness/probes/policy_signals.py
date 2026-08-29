import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from web_openness.client import FetchResult, RequestBudgetExceeded
from web_openness.domains import registrable_domain
from web_openness.models import Confidence, Evidence, Observation, ObservationOutcome, ProbeError
from web_openness.probes.base import ProbeContext, evidence_from_fetch, observation
from web_openness.probes.robots import policy_allows

SIGNAL_KEYS = (
    "legal.scraping_restrictions",
    "legal.ai_restrictions",
    "economic.registration_required",
    "economic.metering",
    "economic.api_pricing",
)
MAX_CANDIDATE_LINKS = 100
MAX_LINK_TEXT_CHARS = 256
MAX_URL_CHARS = 4_096
MAX_DOCUMENT_TEXT_CHARS = 200_000
MAX_DOCUMENT_FETCHES = 2
RESERVED_REQUESTS = 1
MAX_MATCHES_PER_SIGNAL = 10

LEGAL_SCOPE = (
    "legal.scraping_restrictions",
    "legal.ai_restrictions",
    "economic.registration_required",
)
ECONOMIC_SCOPE = (
    "economic.registration_required",
    "economic.metering",
    "economic.api_pricing",
)

SCRAPING_PATTERNS = (
    (
        "automated_access_prohibited",
        re.compile(
            r"\b(?:you|users?|visitors?)\s+(?:may|must|shall|can)\s+not\b"
            r".{0,160}\b(?:scrap(?:e|ing)|crawl(?:er|ing)?|spider(?:ing)?|"
            r"automated (?:means|access|collection|extraction))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "scraping_prohibited",
        re.compile(
            r"\b(?:scrap(?:e|ing)|web craw(?:l|ling|lers?)|"
            r"automated (?:access|collection|extraction))\b.{0,100}"
            r"\b(?:is|are)\s+(?:strictly )?(?:prohibited|forbidden|not permitted)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "automated_tools_prohibited",
        re.compile(
            r"\b(?:do not|don't)\s+(?:use|deploy)\b.{0,100}"
            r"\b(?:robots?|spiders?|scrapers?|crawlers?|automated (?:means|tools?))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "automated_access_requires_permission",
        re.compile(
            r"\b(?:access|collect|extract|download)\b.{0,100}"
            r"\b(?:robots?|spiders?|scrapers?|crawlers?|automated means)\b.{0,100}"
            r"\bwithout\b.{0,60}\b(?:permission|consent)\b",
            re.IGNORECASE,
        ),
    ),
)

AI_PATTERNS = (
    (
        "ai_training_prohibited",
        re.compile(
            r"\b(?:you|users?|third parties)\s+(?:may|must|shall|can)\s+not\b"
            r".{0,80}\b(?:use|copy|collect|extract)\b.{0,100}\b(?:to|for)\b"
            r".{0,40}\b(?:train|training|develop|developing|improve|improving|"
            r"fine[- ]?tune|fine[- ]?tuning)\b.{0,100}"
            r"\b(?:artificial intelligence|machine learning|generative "
            r"(?:artificial intelligence|ai)|large language models?|llms?|ai models?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ai_use_prohibited",
        re.compile(
            r"\b(?:you|users?|third parties)\s+(?:may|must|shall|can)\s+not\b"
            r".{0,80}\b(?:use|copy|collect|extract)\b.{0,100}\b(?:to|for)\b"
            r".{0,40}\b(?:artificial intelligence|machine learning|generative "
            r"(?:artificial intelligence|ai)|large language models?|llms?|ai models?)\b"
            r".{0,40}\b(?:train|training|develop|developing|improve|improving|"
            r"fine[- ]?tune|fine[- ]?tuning)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "content_ai_training_prohibited",
        re.compile(
            r"\b(?:content|materials?|data)\s+(?:may|must|shall|can)\s+not\s+be\s+used\b"
            r".{0,140}\b(?:artificial intelligence|machine learning|generative "
            r"(?:artificial intelligence|ai)|"
            r"large language models?|llms?|ai training)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ai_training_explicitly_prohibited",
        re.compile(
            r"\b(?:ai|artificial intelligence|machine learning|model)\s+training\b"
            r".{0,80}\b(?:is|are)\s+(?:strictly )?"
            r"(?:prohibited|forbidden|not permitted)\b",
            re.IGNORECASE,
        ),
    ),
)

REGISTRATION_REQUIRED_PATTERNS = (
    re.compile(
        r"\b(?:registration|an? (?:user )?account|signing up)\s+"
        r"(?:is|are)\s+(?:required|mandatory)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:you|users?)\s+(?:must|are required to)\s+"
        r"(?:register|create an account|sign up)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:access|use)\b.{0,60}\brequires?\s+"
        r"(?:registration|an account|signing up)\b",
        re.IGNORECASE,
    ),
)
REGISTRATION_NOT_REQUIRED_PATTERNS = (
    re.compile(
        r"\bno (?:registration|account|sign[- ]?up)\s+(?:is )?required\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:access|use|browse)\b.{0,80}\bwithout\s+"
        r"(?:registration|an account|signing up)\b",
        re.IGNORECASE,
    ),
)

METERING_PATTERNS = (
    (
        "periodic_limit",
        re.compile(
            r"\b(?:up to|includes?|limited to|allows?)\s+\d[\d,]*(?:\.\d+)?\s+"
            r"(?:articles?|requests?|api calls?|calls?|queries|credits?|tokens?)\s+"
            r"(?:per|/)\s+(?:second|minute|hour|day|week|month|year)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "explicit_quota",
        re.compile(
            r"\b(?:daily|monthly|annual|hourly)\s+(?:limit|quota)\s+"
            r"(?:of|is)\s+\d[\d,]*(?:\.\d+)?\s+"
            r"(?:articles?|requests?|api calls?|calls?|queries|credits?|tokens?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "metered_access",
        re.compile(r"\bmetered\s+(?:access|plan|usage|billing)\b", re.IGNORECASE),
    ),
)

PRICE_AMOUNT = re.compile(
    r"(?:US\$|USD|EUR|GBP|\$|€|£)\s?\d[\d,]*(?:\.\d{1,2})?"
    r"(?:\s*(?:per|/)\s*(?:request|call|credit|month|year))?",
    re.IGNORECASE,
)
API_PRICE_FORWARD = re.compile(
    r"\bapi(?: access| plan| usage)?\b.{0,50}"
    r"\b(?:costs?|is priced at|starts? at|from)\s*"
    r"(?P<price>(?:US\$|USD|EUR|GBP|\$|€|£)\s?\d[\d,]*(?:\.\d{1,2})?"
    r"(?:\s*(?:per|/)\s*(?:request|call|credit|month|year))?)",
    re.IGNORECASE,
)
API_PRICE_REVERSE = re.compile(
    r"(?P<price>(?:US\$|USD|EUR|GBP|\$|€|£)\s?\d[\d,]*(?:\.\d{1,2})?"
    r"(?:\s*(?:per|/)\s*(?:request|call|credit|month|year))?).{0,60}"
    r"\b(?:for|includes?)\b.{0,40}\bapi(?: access| usage| plan| calls?)\b",
    re.IGNORECASE,
)
API_FREE = re.compile(
    r"(?:\bapi (?:access|usage|plan)\s+(?:is|are)\s+free\b|"
    r"\bfree api (?:access|usage|plan)\b|"
    r"\bfree (?:tier|plan) for (?:the )?api\b)",
    re.IGNORECASE,
)
API_CONTACT_SALES = re.compile(
    r"(?:\bapi (?:pricing|access|plan)\b.{0,50}\bcontact sales\b|"
    r"\bcontact sales (?:for|about) (?:our |the )?api\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Candidate:
    url: str
    score: int
    scope: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Declaration:
    source_url: str
    rule: str
    detail: str | None = None

    def as_dict(self) -> dict[str, str]:
        value = {"source_url": self.source_url, "rule": self.rule}
        if self.detail is not None:
            value["detail"] = self.detail
        return value


@dataclass(slots=True)
class TextFindings:
    scraping: list[Declaration] = field(default_factory=list)
    ai: list[Declaration] = field(default_factory=list)
    registration_required: list[Declaration] = field(default_factory=list)
    registration_not_required: list[Declaration] = field(default_factory=list)
    metering: list[Declaration] = field(default_factory=list)
    api_pricing: list[Declaration] = field(default_factory=list)

    def extend(self, other: "TextFindings") -> None:
        self.scraping.extend(other.scraping)
        self.ai.extend(other.ai)
        self.registration_required.extend(other.registration_required)
        self.registration_not_required.extend(other.registration_not_required)
        self.metering.extend(other.metering)
        self.api_pricing.extend(other.api_pricing)


class _HomepageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._anchor: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        values = {key.lower(): value or "" for key, value in attrs}
        self._anchor = {
            "href": values.get("href", "").strip()[:MAX_URL_CHARS],
            "text": "",
        }

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._anchor is None:
            return
        href = self._anchor["href"]
        text = " ".join(self._anchor["text"].split())[:MAX_LINK_TEXT_CHARS]
        haystack = " ".join((urlsplit(href).path, text)).lower()
        if (
            href
            and (_policy_score(haystack) or _economic_score(haystack))
            and len(self.links) < MAX_CANDIDATE_LINKS
        ):
            self.links.append((href, text))
        self._anchor = None

    def handle_data(self, data: str) -> None:
        if self._anchor is None:
            return
        current = self._anchor["text"]
        self._anchor["text"] = current + data[: MAX_LINK_TEXT_CHARS - len(current)]


class _DocumentTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.chars = 0
        self.truncated = False
        self._ignored_depth = 0

    @property
    def text(self) -> str:
        return " ".join("".join(self.parts).split())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() in {"script", "style", "svg", "template"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "svg", "template"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth or self.truncated:
            return
        remaining = MAX_DOCUMENT_TEXT_CHARS - self.chars
        if remaining <= 0:
            self.truncated = True
            return
        value = f"{' ' if self.parts else ''}{data}"
        chunk = value[:remaining]
        if chunk:
            self.parts.append(chunk)
            self.chars += len(chunk)
        if len(value) > remaining:
            self.truncated = True


class PolicySignalsProbe:
    name = "policy_signals"

    async def collect(self, context: ProbeContext) -> dict[str, Observation]:
        html = context.shared.get("homepage_html")
        homepage_evidence = context.shared.get("homepage_evidence")
        if not isinstance(html, str) or not isinstance(homepage_evidence, Evidence):
            return _unknown_signals(
                "homepage HTML was unavailable",
                outcome=_unavailable_outcome(context),
            )

        response = context.shared.get("homepage_response")
        base_url = (
            response.final_url
            if isinstance(response, FetchResult) and response.final_url
            else context.origin
        )
        findings = TextFindings()
        evidence = [homepage_evidence]
        issues: dict[str, ObservationOutcome] = {}

        homepage_parser = _DocumentTextParser()
        homepage_parser.feed(html)
        findings.extend(analyze_public_text(homepage_parser.text, homepage_evidence.source_url))
        if homepage_parser.truncated or (isinstance(response, FetchResult) and response.truncated):
            _record_issue(issues, SIGNAL_KEYS, ObservationOutcome.ERROR)

        candidates = discover_candidates(html, base_url)
        available = max(
            0,
            context.config.request_budget - len(context.client.records) - RESERVED_REQUESTS,
        )
        selected = candidates[: min(MAX_DOCUMENT_FETCHES, available)]
        for candidate in candidates[len(selected) : MAX_DOCUMENT_FETCHES]:
            _record_issue(issues, candidate.scope, ObservationOutcome.SKIPPED)

        for candidate in selected:
            if not policy_allows(context, candidate.url):
                _record_issue(issues, candidate.scope, ObservationOutcome.SKIPPED)
                continue
            try:
                result = await context.client.get(candidate.url)
            except RequestBudgetExceeded:
                _record_issue(issues, candidate.scope, ObservationOutcome.SKIPPED)
                continue

            candidate_evidence = evidence_from_fetch(
                result,
                note="bounded public policy or pricing text analysis",
            )
            evidence.append(candidate_evidence)
            if result.error is not None:
                context.errors.append(ProbeError(probe=self.name, message=result.error))
                _record_issue(issues, candidate.scope, ObservationOutcome.ERROR)
                continue
            if result.status_code in {404, 410}:
                continue
            if result.status_code != 200:
                _record_issue(issues, candidate.scope, ObservationOutcome.SKIPPED)
                continue
            content_type = result.headers.get("content-type", "").lower()
            if not _supported_text_type(content_type):
                _record_issue(issues, candidate.scope, ObservationOutcome.SKIPPED)
                continue

            parser = _DocumentTextParser()
            if content_type.startswith("text/plain"):
                parser.handle_data(result.text)
            else:
                parser.feed(result.text)
            findings.extend(analyze_public_text(parser.text, candidate_evidence.source_url))
            if result.truncated or parser.truncated:
                context.errors.append(
                    ProbeError(
                        probe=self.name,
                        message=f"policy/pricing text was truncated: {candidate.url}",
                    )
                )
                _record_issue(issues, candidate.scope, ObservationOutcome.ERROR)

        return _observations(findings, evidence, issues)


def discover_candidates(html: str, base_url: str) -> list[Candidate]:
    parser = _HomepageParser()
    parser.feed(html)
    policy: dict[str, Candidate] = {}
    economic: dict[str, Candidate] = {}
    for href, text in parser.links:
        url = _same_site_http_url(base_url, href)
        if url is None:
            continue
        haystack = " ".join((urlsplit(url).path, text)).lower()
        policy_score = _policy_score(haystack)
        economic_score = _economic_score(haystack)
        if policy_score:
            _keep_best_candidate(policy, Candidate(url, policy_score, LEGAL_SCOPE))
        if economic_score:
            _keep_best_candidate(economic, Candidate(url, economic_score, ECONOMIC_SCOPE))

    policy_ranked = sorted(policy.values(), key=lambda item: (-item.score, item.url))
    economic_ranked = sorted(economic.values(), key=lambda item: (-item.score, item.url))
    selected: list[Candidate] = []
    for group in (policy_ranked, economic_ranked):
        if not group:
            continue
        candidate = group[0]
        duplicate = next((item for item in selected if item.url == candidate.url), None)
        if duplicate is None:
            selected.append(candidate)
            continue
        selected[selected.index(duplicate)] = Candidate(
            url=candidate.url,
            score=max(candidate.score, duplicate.score),
            scope=tuple(key for key in SIGNAL_KEYS if key in {*candidate.scope, *duplicate.scope}),
        )
    return selected


def analyze_public_text(text: str, source_url: str) -> TextFindings:
    normalized = " ".join(text.split())[:MAX_DOCUMENT_TEXT_CHARS]
    findings = TextFindings()
    findings.scraping = _rule_matches(normalized, source_url, SCRAPING_PATTERNS)
    findings.ai = _rule_matches(normalized, source_url, AI_PATTERNS)
    findings.registration_required = _presence_matches(
        normalized,
        source_url,
        "registration_required",
        REGISTRATION_REQUIRED_PATTERNS,
    )
    findings.registration_not_required = _presence_matches(
        normalized,
        source_url,
        "registration_not_required",
        REGISTRATION_NOT_REQUIRED_PATTERNS,
    )
    findings.metering = _rule_matches(normalized, source_url, METERING_PATTERNS, detail=True)
    findings.api_pricing = _api_pricing_matches(normalized, source_url)
    return findings


def _observations(
    findings: TextFindings,
    evidence: list[Evidence],
    issues: dict[str, ObservationOutcome],
) -> dict[str, Observation]:
    values = {
        "legal.scraping_restrictions": _declaration_observation(
            findings.scraping,
            "explicit public prohibition on scraping or automated access",
            evidence,
        ),
        "legal.ai_restrictions": _declaration_observation(
            findings.ai,
            "explicit public prohibition on AI/model training or use",
            evidence,
        ),
        "economic.registration_required": _registration_observation(findings, evidence),
        "economic.metering": _declaration_observation(
            findings.metering,
            "explicit numeric quota or metered-access declaration",
            evidence,
        ),
        "economic.api_pricing": _declaration_observation(
            findings.api_pricing,
            "explicit API price, free tier, or contact-sales declaration",
            evidence,
        ),
    }
    for key, outcome in issues.items():
        if values[key].outcome != ObservationOutcome.NO_EVIDENCE:
            continue
        method = (
            "relevant public text could not be completely analyzed"
            if outcome == ObservationOutcome.ERROR
            else "relevant public text was skipped by robots or the bounded request budget"
        )
        values[key] = observation(
            None,
            confidence=Confidence.UNKNOWN,
            score=0.0,
            method=method,
            evidence=evidence,
            outcome=outcome,
        )
    return values


def _declaration_observation(
    declarations: list[Declaration],
    method: str,
    evidence: list[Evidence],
) -> Observation:
    values = _unique_declarations(declarations)
    return observation(
        {"detected": True, "declarations": values} if values else None,
        confidence=Confidence.CONFIRMED if values else Confidence.NO_EVIDENCE,
        score=1.0,
        method=method if values else f"no {method} in bounded examined sources",
        evidence=_matching_evidence(evidence, values) if values else evidence,
    )


def _registration_observation(findings: TextFindings, evidence: list[Evidence]) -> Observation:
    required = _unique_declarations(findings.registration_required)
    not_required = _unique_declarations(findings.registration_not_required)
    if required and not_required:
        return observation(
            None,
            confidence=Confidence.UNKNOWN,
            score=0.0,
            method="conflicting explicit registration declarations in examined sources",
            evidence=_matching_evidence(evidence, [*required, *not_required]),
            outcome=ObservationOutcome.ERROR,
        )
    declarations = required or not_required
    if declarations:
        return observation(
            bool(required),
            confidence=Confidence.CONFIRMED,
            score=1.0,
            method="explicit public registration requirement declaration",
            evidence=_matching_evidence(evidence, declarations),
        )
    return observation(
        None,
        confidence=Confidence.NO_EVIDENCE,
        score=1.0,
        method="no explicit registration requirement declaration in bounded examined sources",
        evidence=evidence,
    )


def _unknown_signals(method: str, *, outcome: ObservationOutcome) -> dict[str, Observation]:
    return {
        key: observation(
            None,
            confidence=Confidence.UNKNOWN,
            score=0.0,
            method=method,
            outcome=outcome,
        )
        for key in SIGNAL_KEYS
    }


def _unavailable_outcome(context: ProbeContext) -> ObservationOutcome:
    if context.shared.get("robots_allows_followup") is not True:
        return ObservationOutcome.SKIPPED
    response = context.shared.get("homepage_response")
    if (
        isinstance(response, FetchResult)
        and response.error is None
        and response.status_code is not None
    ):
        return ObservationOutcome.SKIPPED
    return ObservationOutcome.ERROR


def _supported_text_type(content_type: str) -> bool:
    return content_type.startswith(("text/html", "application/xhtml+xml", "text/plain"))


def _same_site_http_url(base_url: str, href: str) -> str | None:
    resolved = urljoin(base_url, href)
    parsed = urlsplit(resolved)
    base = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or base.hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    try:
        same_site = registrable_domain(parsed.hostname) == registrable_domain(base.hostname)
    except ValueError:
        same_site = parsed.hostname.lower().rstrip(".") == base.hostname.lower().rstrip(".")
    if not same_site:
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))


def _policy_score(haystack: str) -> int:
    normalized = "-".join(re.findall(r"[a-z0-9]+", haystack))
    if any(marker in normalized for marker in ("scraping-policy", "ai-policy")):
        return 120
    if any(
        marker in normalized for marker in ("acceptable-use", "terms-of-service", "terms-of-use")
    ):
        return 110
    tokens = set(re.findall(r"[a-z0-9]+", haystack))
    if "aup" in tokens:
        return 105
    if "terms" in tokens:
        return 90
    if "legal" in tokens:
        return 70
    return 0


def _economic_score(haystack: str) -> int:
    normalized = "-".join(re.findall(r"[a-z0-9]+", haystack))
    tokens = set(re.findall(r"[a-z0-9]+", haystack))
    if "api-pricing" in normalized:
        return 120
    if tokens & {"pricing", "prices", "plans"}:
        return 105 if "api" in tokens else 100
    if "registration-requirements" in normalized:
        return 90
    if "api-docs" in normalized or "developer-docs" in normalized:
        return 70
    if tokens & {"developers", "developer"}:
        return 50
    return 0


def _keep_best_candidate(candidates: dict[str, Candidate], candidate: Candidate) -> None:
    existing = candidates.get(candidate.url)
    if existing is None or candidate.score > existing.score:
        candidates[candidate.url] = candidate


def _record_issue(
    issues: dict[str, ObservationOutcome],
    keys: tuple[str, ...],
    outcome: ObservationOutcome,
) -> None:
    for key in keys:
        if issues.get(key) == ObservationOutcome.ERROR:
            continue
        issues[key] = outcome


def _rule_matches(
    text: str,
    source_url: str,
    patterns: tuple[tuple[str, re.Pattern[str]], ...],
    *,
    detail: bool = False,
) -> list[Declaration]:
    matches: list[Declaration] = []
    for rule, pattern in patterns:
        found = pattern.search(text)
        if found is not None:
            value = " ".join(found.group(0).split())[:160] if detail else None
            matches.append(Declaration(source_url=source_url, rule=rule, detail=value))
    return matches[:MAX_MATCHES_PER_SIGNAL]


def _presence_matches(
    text: str,
    source_url: str,
    rule: str,
    patterns: tuple[re.Pattern[str], ...],
) -> list[Declaration]:
    return [
        Declaration(source_url=source_url, rule=rule)
        for pattern in patterns
        if pattern.search(text) is not None
    ][:MAX_MATCHES_PER_SIGNAL]


def _api_pricing_matches(text: str, source_url: str) -> list[Declaration]:
    declarations: list[Declaration] = []
    for pattern in (API_PRICE_FORWARD, API_PRICE_REVERSE):
        for match in pattern.finditer(text):
            price = match.group("price")
            if PRICE_AMOUNT.fullmatch(price):
                declarations.append(
                    Declaration(
                        source_url=source_url,
                        rule="published_api_price",
                        detail=" ".join(price.split())[:80],
                    )
                )
    if API_FREE.search(text):
        declarations.append(Declaration(source_url=source_url, rule="free_api_tier"))
    if API_CONTACT_SALES.search(text):
        declarations.append(Declaration(source_url=source_url, rule="api_contact_sales"))
    return declarations[:MAX_MATCHES_PER_SIGNAL]


def _unique_declarations(declarations: list[Declaration]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str | None]] = set()
    values: list[dict[str, str]] = []
    for declaration in declarations:
        key = (declaration.source_url, declaration.rule, declaration.detail)
        if key in seen:
            continue
        seen.add(key)
        values.append(declaration.as_dict())
        if len(values) >= MAX_MATCHES_PER_SIGNAL:
            break
    return values


def _matching_evidence(
    evidence: list[Evidence], declarations: list[dict[str, str]]
) -> list[Evidence]:
    source_urls = {value["source_url"] for value in declarations}
    return [item for item in evidence if item.source_url in source_urls]
