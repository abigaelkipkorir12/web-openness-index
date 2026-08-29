# Plot roadmap

Plots should make data quality visible before they make substantive claims. Every figure must state its domain population, measurement wave, denominator, weighting rule, missing-data treatment, collector revision, and detector version.

## Required inputs

- `runs.csv`: one row per scan with timing, request, outcome, and error counts;
- `observations.csv`: one row per domain-signal result with outcome, confidence, value, and method;
- `changes.csv`: the latest repeated-scan comparison for each shared domain and signal;
- the frozen selection manifest: sector, geography, popularity band, source, and inclusion probability;
- detector-validation labels and predictions for any inferred measure.

Join research tables by canonical domain and scan/run identifier. Keep `observed`, `no_evidence`, `skipped`, and `error` separate through aggregation.

## First figures: can we trust the data?

| Figure | Question | Recommended form |
| --- | --- | --- |
| 1. Outcome coverage | Which signal families produce interpretable results? | Heatmap of outcome shares by family and sampling stratum |
| 2. Collection disposition | Did domains complete, deny, defer, opt out, or fail? | Stacked bars by sector, geography, and popularity band |
| 3. Request burden | How much traffic did measurement create? | Distribution of HTTP/browser requests per domain with limits marked |
| 4. Failure profile | Where do errors, HTTP 403, and HTTP 429 occur? | Small-multiple rates with counts and confidence intervals |
| 5. Detector validity | Which inferred signals are reliable? | Precision, recall, and abstention by detector and stratum |
| 6. Repeatability | Which results change between close repeat scans? | Changed-share plot by signal family and outcome transition matrix |

These figures are release gates. If they expose systematic missingness, detector failure, policy violations, or unexplained instability, pause scoring and fix the measurement.

## Descriptive research figures

| Figure | Question | Recommended form |
| --- | --- | --- |
| 7. Access profiles | How do human, crawler, and agent access differ? | Separate dimension distributions or dot plots; no composite required |
| 8. AI crawler policy | Which named AI agents are allowed or disallowed? | Agent-by-sector policy heatmap with unknowns shown |
| 9. Human barriers | How common are login, paywall, consent, CAPTCHA, and JavaScript markers? | Prevalence dot plots by stratum using validated detectors only |
| 10. Machine interfaces | Where are APIs, OpenAPI, GraphQL, MCP, A2A, or agent cards discoverable? | Candidate and verified rates shown as separate series |
| 11. Infrastructure and access | Are provider or protection hints associated with access outcomes? | Adjusted or stratified comparisons; label them associational |
| 12. Legal and economic conditions | Where are explicit scraping, AI-use, registration, subscription, metering, or pricing declarations found? | Prevalence dot plots with method coverage beside each estimate |
| 13. Preservation | Which domains expose cache evidence or public-archive coverage? | Coverage and access-state bars by stratum |
| 14. Metadata availability | Which machine-readable formats are published? | Co-occurrence matrix for JSON-LD, feeds, sitemap, Open Graph, and `llms.txt` |

Candidate discovery must not be plotted as verified capability. Provider hints must not be plotted as exact product configuration. Legal-language detection must not be presented as legal advice or a complete reading of a site's terms.

## Longitudinal figures

After at least two comparable waves:

1. Plot within-domain transitions among observed access states, including transitions to missing outcomes.
2. Plot weighted wave estimates with uncertainty for the fixed panel and refresh sample separately.
3. Show entries, exits, and permanent ineligibility rather than dropping them from the denominator.
4. Mark collector, detector, schema, or sampling changes on every trend.
5. Run a bridge sample across method changes before interpreting a discontinuity as web change.

## Minimal figure contract

Each saved plot should have a companion data file or script that records:

- the exact input manifest and snapshot set;
- filters and exclusions;
- numerator and denominator;
- weighting and uncertainty method;
- missingness counts;
- code and methodology revisions;
- a plain-language caption stating what the figure does and does not show.

Begin with static, reproducible figures. Add an interactive dashboard only after the tables and interpretations are stable.
