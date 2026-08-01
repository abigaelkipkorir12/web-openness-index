# Pilot sampling methodology

## Purpose and estimand

The pilot should test whether the observatory can make reproducible, longitudinal measurements across a heterogeneous web population. Its primary estimand is the domain-weighted prevalence or mean of each access measure among eligible domains in a frozen sampling frame. It is not an estimate for pages, organizations, traffic, users, or the entire web beyond that frame. Traffic-weighted and organization-level estimates may be reported separately, with their assumptions stated.

The pilot is intended to estimate coverage, missingness, stratum variance, detector performance, and operational cost. Its balanced design is not, by itself, a claim of population representativeness.

## Sampling unit and measurement target

The primary sampling unit is a registrable domain (the effective top-level domain plus one label, evaluated with a frozen Public Suffix List). Internationalized names are stored in both Unicode and canonical ASCII form. Each registrable domain appears once in a wave, even if it enters through several sources.

Collection begins from a declared canonical public URL, normally `https://<domain>/`. Redirects are followed only under collection policy and recorded; they do not change the identity of the sampled unit. Relevant host-level observations may be retained beneath the domain record. Multiple domains controlled by one organization remain distinct units, but known organizational clustering should be recorded for sensitivity analyses.

## Target population and eligibility

The operational target population is publicly addressable web domains represented in the versioned frame at its freeze date. A domain is eligible when it:

- is a valid registrable domain in the frozen Public Suffix List;
- appears in at least one enumerated, documented frame source;
- resolves through public DNS to a destination allowed by the collector's network-safety policy; and
- is not an exact or canonicalized duplicate of another frame entry.

HTTP errors, `robots.txt` restrictions, login requirements, paywalls, CAPTCHAs, and JavaScript requirements do not make a domain ineligible; they are access outcomes. A domain that was eligible when the frame was frozen remains in the sample if it later becomes unreachable, so attrition is not mistaken for openness. Parked domains should be flagged rather than removed unless the preregistered target population excludes them.

Exclude public suffixes, malformed names, private or link-local destinations, metadata-service addresses, test fixtures, and domains whose collection would violate applicable law or a documented safety protocol. Any safety-based scope exclusion must use a content-neutral rule and be reported by stratum. Hand-picked domains may be used in a separate detector-validation set, but never silently mixed into the probability sample.

## Building a reproducible frame

Construct the candidate frame from a frozen union of sources that have enumerable membership and compatible use terms. The union should include:

1. a reproducible popularity-ranking snapshot for head and middle coverage;
2. public or licensed registered-domain lists, zone-derived lists, or other broad enumerations for the long tail; and
3. documented sector directories for coverage of government, academic, news, commerce, and community services.

Source choice affects coverage and must be treated as part of the methodology. The pilot should not generalize to domains absent from all chosen sources. Source-overlap counts and coverage limitations should accompany every result.

Assign each candidate one primary sampling sector and geography using frozen rules. Preserve secondary labels and classification confidence. The initial sector ontology is:

- news and media;
- government and civic services;
- academia and research;
- commerce and commercial services;
- forums and online communities; and
- general or other.

Geography should use the five UN-style macro-regions (Africa, Americas, Asia, Europe, and Oceania), plus a `global_or_unassigned` stratum. Assignment should follow the service's documented institutional location or primary audience, not hosting location or top-level domain alone. Ambiguous cases remain in `global_or_unassigned`; they are not forced into a country.

Use three initial popularity bands based on the frozen ranking source:

- **head:** ranks 1–10,000;
- **middle:** ranks 10,001–100,000; and
- **long tail:** rank above 100,000 or absent from the ranking but present in another enumerated frame source.

These thresholds are pilot conventions, not natural categories. Report sensitivity to alternative cutoffs. Before drawing the sample, freeze an immutable frame manifest containing at least:

- frame and schema versions, creation time, code revision, and random seed;
- source names, retrieval dates, licenses or access terms, original checksums, and source-membership flags;
- canonical domain, Public Suffix List version, and deduplication decision;
- sector, geography, popularity band, classification method, provenance, and confidence;
- eligibility state and exclusion reason; and
- stratum size, randomized order, selection indicator, and inclusion probability.

Given the same inputs, code revision, and seed, selection must reproduce the same ordered sample. Publish the selection manifest and source metadata when licensing permits; otherwise publish hashes and executable reconstruction instructions.

## First stratified pilot

Use the full cross-product of six sectors, six geography groups, and three popularity bands. Draw four domains without replacement from each cell for a target baseline of **432 domains** (`6 × 6 × 3 × 4`). Within a cell, use a seeded uniform random draw from the deduplicated eligible frame. Do not replace a sparse cell with a convenient domain from another cell: record its shortfall and keep the achieved allocation visible.

The design deliberately oversamples smaller sectors, regions, and the long tail to expose failure modes. Unweighted pilot summaries describe the achieved balanced sample, not the frame. Frame-level summaries require design weights.

Recommended phases are:

| Phase | Target | Purpose | Exit condition |
| --- | ---: | --- | --- |
| Canary | 24–36 domains, outside the analytic sample | Verify safety controls, request budgets, schemas, and evidence writes | No policy violations; all artifacts validate |
| Baseline pilot | 432 domains | Estimate feasibility, missingness, cost, and between-stratum variation | Quality gates below pass or exceptions are documented |
| Replication | Two additional waves of the same design | Measure repeatability and short-term attrition | Temporal disagreement and collection drift are quantified |
| Expansion | Approximately 1,500–3,000 domains | Support planned subgroup and trend estimates | Size justified from pilot variance, design effects, and precision targets |

The expansion size should be calculated from preregistered target precision or minimum detectable change, adjusted for unequal weights, clustering, nonresponse, repeated measures, and multiple comparisons. The pilot's 432-domain target is for coverage and calibration, not a universal power guarantee.

## Longitudinal panel and refresh sample

At baseline, all selected domains enter the panel. In later waves, retain a fixed **80% panel** and draw a **20% refresh sample** within each stratum from the current frame. Freeze the panel/refresh assignment with the baseline manifest. The panel estimates within-domain change; the refresh sample represents entry and composition changes and helps diagnose panel aging.

Do not drop panel members because a scan fails or a site becomes less accessible. Retire a unit only after a preregistered permanent-ineligibility rule is met, and preserve the retirement event. Replacements belong to the refresh sample and must not rewrite panel history. Report cross-sectional estimates from each wave's current frame separately from longitudinal estimates on the continuing panel.

## Weighting and missingness

For stratum `h`, with `N_h` eligible frame domains and `n_h` sampled domains, the base inclusion probability is `pi_h = min(1, n_h / N_h)` and the base weight is `1 / pi_h`. If the achieved sample differs from the allocation, calculate weights from the achieved draw, not the target. Account explicitly for certainty units, sparse cells, source-specific selection stages, and duplicate-source membership.

Define outcomes before analysis:

- **substantive access outcome:** an observed denial, block, policy restriction, authentication boundary, or protocol failure attributable to the target;
- **structural skip:** a probe not attempted because the declared policy prohibited it;
- **collection missingness:** no interpretable result because of collector, network, or evidence failure; and
- **ineligibility:** the unit did not satisfy the frozen eligibility rule.

Never encode an unknown or failed measurement as an open or closed result. Report unweighted counts and weighted rates of each outcome overall and by stratum. A simple nonresponse adjustment may redistribute weights among completed eligible units within predefined cells, but only with a stated missing-at-random assumption. If completion depends plausibly on openness, publish unadjusted estimates plus sensitivity bounds or models; do not rely on a single imputed value. Design-based standard errors should reflect stratification, unequal weights, finite-population correction where appropriate, and repeated observations for panel analyses.

## Ethics, opt-out, and burden

Collection must remain limited to public interfaces and must not circumvent access controls. Use a transparent user agent and contact page, honor applicable `robots.txt` rules, cap requests and bytes per domain, rate-limit conservatively, avoid authenticated actions, and never bypass paywalls, CAPTCHAs, or geographic controls. Store only evidence needed for measurement; redact tokens, cookies, personal data, and sensitive query strings.

Publish an accessible correction and opt-out channel. Authenticate control claims proportionately, record the request and effective date, and stop future collection promptly when an opt-out is accepted. Preserve only the minimum audit metadata needed to explain resulting coverage changes. Opt-outs must be reported as a distinct disposition rather than recoded as ordinary nonresponse. The policy for already-released aggregates and historical raw evidence requires ethics and legal review before the pilot.

## Pilot quality gates

The baseline is suitable for analytic use only when:

1. the frame, selection manifest, code revision, seed, and source checksums reproduce the selected sample exactly;
2. canonical domains are unique, every inclusion and exclusion is auditable, and all selected units have known inclusion probabilities;
3. a blinded manual audit covers at least 10% of sampled sector and geography assignments, with disagreements and classification uncertainty reported;
4. there are zero request-budget, network-safety, access-control-circumvention, or evidence-overwrite violations;
5. 100% of emitted snapshots validate against the declared schema, and all artifacts link to method and detector versions;
6. collection disposition is known for every sampled unit, with at least 90% interpretable completion overall and 75% in every non-sparse stratum, or the pilot is explicitly labeled operationally incomplete;
7. missingness, opt-outs, and exclusions are reported by sector, geography, popularity band, and source membership;
8. any detector used in an index has a preregistered labeled validation set, uncertainty estimates, abstention behavior, and an acceptance threshold appropriate to its use; and
9. replicate scans quantify measurement instability, while collector or detector changes are tested for discontinuities before longitudinal comparisons.

Failure of a gate should pause scoring or generalization, not erase the affected observations. Raw evidence and disposition records remain useful for diagnosing the design.

## Decisions intentionally left open

The pilot should inform, not preempt, the following decisions:

- exact frame sources, redistribution constraints, popularity measure, and rank cutoffs;
- whether parked, adult, high-risk, and non-browser services belong in the target population;
- sector ontology, treatment of multi-sector domains, geography rules, and manual-review protocol;
- organization-level deduplication and treatment of subdomains or country-specific properties;
- scan vantage points and whether geography-specific access requires a separate sampling dimension;
- final allocation, panel rotation rate, replacement and permanent-ineligibility rules;
- primary estimands, weighting calibration, nonresponse models, and precision targets;
- evidence retention, screenshots, correction handling, and treatment of historical records after opt-out; and
- scoring dimensions, detector acceptance thresholds, index weights, and aggregation rules.

Each resolved choice should receive a methodology version and, where it changes an earlier release, a documented comparability assessment.
