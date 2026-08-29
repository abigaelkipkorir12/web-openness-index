# Measurement coverage

The operational registry contains **110 signals in ten families**. Each key has code that can collect a result, record no evidence, or explain why collection was skipped. The canonical list is [`src/web_openness/signals.py`](../src/web_openness/signals.py).

This count describes software coverage, not scientific validity. A DNS answer is direct evidence; a vendor fingerprint is an inference; a link named “API” is only a candidate. These should not receive equal treatment in analysis or scoring.

## Evidence classes

| Class | Meaning | Example |
| --- | --- | --- |
| Direct | The scanner observed the reported protocol or response fact. | HTTP status, TLS version, `robots.txt` rule |
| Explicit declaration | The site stated the condition in bounded public text or metadata. | `requiresSubscription`, stated API price |
| Conservative inference | Multiple high-precision markers suggest a condition. | CDN or paywall hint |
| Candidate discovery | A public link or conventional path may expose an interface. | OpenAPI or MCP link |
| Optional measurement | The method adds cost, third-party traffic, or interpretive risk and is off by default. | Browser render, Wayback lookup, cache validation |

Every observation retains its method, confidence, outcome, and minimal evidence. `no_evidence` means “not found by this method,” not “the condition is false.”

## Families

| Family | Keys | What is collected | Main limitation | Primary modules |
| --- | ---: | --- | --- | --- |
| Network | 16 | Public DNS, TLS certificate and negotiation, HTTP version | A single vantage point does not establish global behavior | [`network.py`](../src/web_openness/probes/network.py), [`dns_metadata.py`](../src/web_openness/probes/dns_metadata.py) |
| Infrastructure | 21 | Response/security/cache headers; CDN, edge, WAF, bot, load-balancer, DNS, and hosting hints | Fingerprints rarely prove an exact product or enabled feature set | [`response.py`](../src/web_openness/probes/response.py) |
| Crawler | 12 | `robots.txt`, AI-agent groups, crawl delays, sitemaps, policy decisions, 403/429 frequencies, HTTP/browser difference | One declared identity and one bounded path set do not represent every crawler | [`robots.py`](../src/web_openness/probes/robots.py), [`sitemap.py`](../src/web_openness/probes/sitemap.py), [`http_attempts.py`](../src/web_openness/probes/http_attempts.py) |
| Browser | 3 | Optional navigation, rendered-document summary, and request/transfer summary | Non-interactive rendering cannot establish that a barrier is impossible to pass | [`browser.py`](../src/web_openness/probes/browser.py) |
| Human | 17 | Homepage reachability plus conservative login, rate-limit, paywall, cookie-wall, CAPTCHA, JavaScript, and possible geography markers | Most barrier classifiers need labeled validation; HTTP 451 is not proof of cause | [`homepage.py`](../src/web_openness/probes/homepage.py), [`page_signals.py`](../src/web_openness/probes/page_signals.py), [`browser.py`](../src/web_openness/probes/browser.py) |
| Metadata | 17 | Sitemap structure, JSON-LD types, Open Graph, feeds, title/language/canonical links, generators, manifests, OpenSearch, `llms.txt` | Presence measures discoverability, not completeness or correctness | [`metadata.py`](../src/web_openness/probes/metadata.py), [`well_known.py`](../src/web_openness/probes/well_known.py) |
| Agent | 9 | Candidate OpenAPI, GraphQL, OAuth, MCP, A2A, agent-card, API-documentation, and TollBit interfaces | Candidates are not authenticated, exercised, or assumed functional | [`metadata.py`](../src/web_openness/probes/metadata.py), [`dns_metadata.py`](../src/web_openness/probes/dns_metadata.py) |
| Legal | 5 | Candidate policy/license links and explicit license, scraping, or AI-use statements from one bounded follow-up | Rule-based extraction is not comprehensive legal interpretation | [`policy_signals.py`](../src/web_openness/probes/policy_signals.py) |
| Economic | 6 | Candidate pricing/registration links and explicit subscription, registration, metering, or API-price statements | One bounded page may miss tiers, exceptions, or negotiated access | [`policy_signals.py`](../src/web_openness/probes/policy_signals.py) |
| Preservation | 4 | Cache headers plus optional Wayback coverage/block evidence and conditional cache behavior | One archive and one request do not establish long-term preservability | [`preservation.py`](../src/web_openness/probes/preservation.py) |

## What the collector can support now

The following are suitable for a bounded pilot and missingness analysis, with method labels retained:

- request volume, status, error, retry, redirect, and policy-skip diagnostics;
- DNS, TLS, HTTP, header, `robots.txt`, sitemap, and declared metadata summaries;
- prevalence of explicit declarations found by the bounded methods;
- candidate-interface discovery rates;
- conservative barrier and infrastructure hints reported as hints;
- comparisons of outcomes across a frozen sample and repeated scans.

The following require more validation before strong claims or scores:

- active, soft, and hard human-barrier classification;
- exact CDN, WAF, bot-management, or vendor feature configuration;
- whether a discovered agent interface is usable and at what capability level;
- comprehensive legal rights or restrictions;
- complete economic access cost;
- archive completeness or general cache behavior;
- any composite openness ranking.

## Validation priorities

| Priority | Work | Pass condition |
| --- | --- | --- |
| 1 | Label human-barrier, infrastructure, legal, and economic fixtures | Precision, recall, and abstention reported on held-out examples |
| 2 | Audit direct protocol parsers and negative cases | Expected results across valid, absent, malformed, blocked, and timed-out fixtures |
| 3 | Verify a sample of agent-interface candidates | Candidate precision reported separately from interface usability |
| 4 | Repeat canary scans | Request limits hold; schema validity is 100%; instability is quantified |
| 5 | Audit missingness by sampling stratum | No skip or error is silently encoded as a substantive access result |

Authenticated interface testing, screenshots, full-site crawling, access-control circumvention, and generalized legal conclusions are outside the current collector.

See [the plot roadmap](plots.md) for the figures these measurements can support and [the scoring draft](methodology/scoring.md) for the gates required before an index.
