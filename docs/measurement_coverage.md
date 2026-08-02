# Measurement coverage

This page maps the current collector to the original research specification. “Implemented” means
the collector emits direct evidence or a deliberately conservative inference. “Partial” means it
emits a candidate or hint but cannot yet establish the full research claim. A missing signal is
never converted to `false`.

The operational catalog now has an implementation path for **all 110 keys**. This is software
coverage, not completion of the research program: some probes are opt-in, and several findings are
supporting metadata, explicit declarations, or deliberately probabilistic hints.

At the original Priority-1 requirement-group level, the collector has **23 fully implemented, 7
partial, and 0 not yet supported**. Browser-versus-HTTP comparison is now implemented. Human barrier
classification remains partial: the renderer can confirm visible high-precision login, paywall,
consent, and CAPTCHA markers, but it does not interact with or attempt to bypass them.

## Priority 1

| Area | Implemented | Partial | Not yet supported |
| --- | --- | --- | --- |
| Human access | HTTP and browser homepage reachability; visible rendered login, paywall, consent, and CAPTCHA markers | Active/soft/hard barrier classification, geographic restriction, JavaScript requirement | — |
| Crawler access | `robots.txt`, AI-agent rules, crawl delay, user-agent targeting, sitemap discovery, scan-wide HTTP status distribution, 403 rate, 429 rate, browser-versus-HTTP comparison | — | — |
| Infrastructure | DNS and hosting hints, CDN/edge hints, explicit WAF/challenge hints, TLS, HTTP version | Exact vendor product and feature configuration is intentionally not inferred without direct evidence | — |
| Public metadata | JSON-LD/Schema.org types, Open Graph, RSS/Atom/JSON Feed links, sitemap, `robots.txt`, `llms.txt` | — | — |

HTTP 451 is recorded as a possible geographic or jurisdictional restriction, not proof of the
site's reason. Barrier markup and vendor fingerprints similarly retain confidence and method
labels rather than being promoted to facts.

## Later priorities

| Area | Current evidence | Main gap |
| --- | --- | --- |
| Agent access | Bounded candidate links for OpenAPI, GraphQL, OAuth, API docs, MCP, A2A, and agent cards | Safe verification, structured commerce, and the capability ladder |
| Legal access | Candidate policy/license links plus explicit scraping and AI-use restrictions from one bounded policy follow-up | Labeled validation, broader policy coverage, and commercial/research-use taxonomy |
| Economic access | Candidate links plus explicit registration, metering, subscription, and API-price declarations from one bounded follow-up | Labeled validation and broader free/enterprise/context classification |
| Preservation | Cache headers, optional monthly-collapsed Wayback coverage/block evidence, and optional conditional cache validation | Archive-provider breadth, validation, and ephemeral-content indicators |
| Research outputs | Immutable snapshots, reproducible stratified selection manifests, analysis-ready CSV exports, repeated-scan comparisons, and a scoring preregistration draft | Detector validation, weighted estimates, screenshots, public API, and dashboard |

## Interpretation

The collector is suitable for a bounded pilot and missingness analysis. A defensible openness index
still requires a frozen real sampling frame, detector validation sets, preregistered weights and
coverage thresholds, repeated waves, and a reviewed public-release methodology.
