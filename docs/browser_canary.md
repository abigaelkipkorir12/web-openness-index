# Browser canary: 2026-08-02

This diagnostic exercised one policy-aware homepage render for eight manually reviewed public
domains: `example.org`, `wikipedia.org`, `arxiv.org`, `github.com`, `cloudflare.com`, `medium.com`,
`bbc.com`, and `nasa.gov`. Domains ran sequentially with the default transparent collector identity,
robots decision, cease-list support, and browser limits. The worker did not click, type,
authenticate, bypass barriers, take screenshots, or retain page content.

The run is a robustness check, not a research sample or a comparison of the sites. Results can
change with time, geography, and egress address.

## Baseline result

The eight scans completed without a top-level failure. The browser obtained a rendered document
for every domain, but the canary exposed two correctness problems:

- Concurrent route callbacks could pass the request checks while DNS validation was in flight.
  Authorized request counts therefore exceeded the configured limits on five domains.
- BBC ended at Chromium's internal `chrome-error://chromewebdata/` page after the overrun, while the
  initial response status still caused the navigation to be reported as collected.

| Domain | Authorized requests | Third-party requests | Rendered result |
| --- | ---: | ---: | --- |
| example.org | 1 | 0 | normal page |
| wikipedia.org | 5 | 0 | normal page |
| arxiv.org | 16 | 0 | normal page |
| github.com | 49 | 48 | normal page |
| cloudflare.com | 39 | 1 | normal page |
| medium.com | 110 | 1 | normal page |
| bbc.com | 85 | 83 | Chromium error page |
| nasa.gov | 59 | 6 | normal page |

The baseline report is under
`/private/tmp/web-openness-browser-canary-20260802/reports/2026-08-02/` on the machine that ran the
canary.

## Corrections and verification

The request gate now reserves capacity before asynchronous address validation, rolls the
reservation back if validation fails, and serializes the reservation itself. Deterministic tests
start concurrent first- and third-party authorizations and confirm that neither limit can
overshoot. The adapter and probe also reject non-HTTP(S) browser error
pages. HTTP-versus-browser comparisons now leave change fields unknown when the direct HTTP result
is missing instead of treating missing evidence as denied access.

The five domains that exceeded a limit were then rerun sequentially:

| Domain | Authorized requests | Third-party requests | Blocked requests | Rendered result |
| --- | ---: | ---: | ---: | --- |
| github.com | 11 | 10 | 101 | normal page |
| cloudflare.com | 30 | 1 | 36 | normal page |
| medium.com | 30 | 1 | 258 | normal page |
| bbc.com | 12 | 10 | 89 | normal page |
| nasa.gov | 30 | 1 | 46 | normal page |

All five respected the configured maximum of 30 authorized requests and 10 third-party requests.
All returned an HTTP(S) final URL with no browser probe error. The verification report is under
`/private/tmp/web-openness-browser-canary-rerun-20260802/reports/2026-08-02/` on the canary machine.

## Measurement findings

- Medium returned HTTP 403 to the direct client and HTTP 200 in the bounded browser context. This
  is a useful browser-versus-HTTP observation, not by itself proof of a general access policy.
- The direct arXiv homepage result was unavailable after its politeness state deferred follow-up
  work, while the browser obtained HTTP 200. Missing direct evidence must not be classified as an
  access-disposition change.
- None of the eight rendered homepages exposed one of the current high-precision visible login,
  paywall, consent-wall, or CAPTCHA selectors. This is `no_evidence`, not evidence that a site has
  no barrier. For example, BBC's bounded HTTP markup contained a paywall-related resource hint but
  did not show a visible paywall selector in the browser pass.
- Three rerun pages reached the 30-request ceiling and two reached the 10-third-party ceiling while
  still producing useful rendered metadata. The current limits are conservative but viable for a
  pilot; raising them is not supported by this canary.

The next browser validation should use labeled local fixtures for visible and hidden barriers.
Live sites are appropriate for drift and safety checks, but not stable detector assertions.
