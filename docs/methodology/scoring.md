# Scoring proposal for the pilot

This is a preregistration draft, not an implemented leaderboard. The pilot should validate detector
accuracy, missingness, and stability before publishing a composite score.

## Unit and dimensions

Score one frozen registrable-domain observation per wave. Report four dimensions separately before
considering a composite:

1. **Human access:** public homepage reachability and observed access barriers.
2. **Crawler access:** robots policy and HTTP/browser access for the declared research identity.
3. **Agent access:** discoverable machine interfaces and the unauthenticated portion of the
   capability ladder.
4. **Preservation:** explicit caching evidence and independently measured public-archive access.

Infrastructure vendors are explanatory covariates, not openness points. Legal and economic access
should be reported as their own outcomes until policy extraction is validated well enough to join a
dimension.

## Signal transforms

Each accepted detector must have a versioned transform from evidence to a bounded value in `[0, 1]`.
The initial convention is:

- `1`: the preregistered public access condition was directly observed;
- `0`: a directly observed policy or technical condition denied that access;
- an intermediate value: only for an ordered capability level or a preregistered partial-access
  state, never merely because confidence is lower;
- missing: skipped, errored, inconclusive, or unsupported observations.

Confidence changes whether a detector is eligible for scoring; it does not mechanically discount a
value. This avoids turning weak guesses into precise-looking fractional scores.

## Dimension estimates

For domain `i` and dimension `d`, calculate the weighted mean only across preregistered, validated
signals observed for that domain:

`D_id = sum_j(a_j * x_ij) / sum_j(a_j)`

where `a_j` is a fixed signal weight and `x_ij` is observed. Publish alongside every dimension:

- the number and total weight of expected signals;
- observed, no-evidence, skipped, and error counts;
- the resulting measurement-coverage fraction; and
- which detector versions contributed.

Do not publish `D_id` below a preregistered coverage threshold. The pilot should compare equal signal
weights with expert weights; if substantive rankings change materially, publish dimensions without
a composite.

## Population estimates

Domain-level summaries do not by themselves describe the frame. Estimate stratum and overall means
with the inclusion probabilities in the frozen selection manifest. Keep these distinct:

- unweighted achieved-sample summaries for operational diagnosis;
- design-weighted frame estimates for cross-sectional claims;
- continuing-panel estimates for within-domain change; and
- refresh-sample estimates for changes in frame composition.

Report uncertainty from stratification and unequal weights. Unknown outcomes remain missing. Present
unadjusted estimates plus explicit sensitivity bounds before using a nonresponse adjustment whose
missing-at-random assumption may be implausible.

## Validation gates

A signal may enter a score only after a labeled audit establishes its target construct, abstention
behavior, and error rates on relevant strata. The preregistration must set per-signal acceptance
thresholds before examining index results. Also require:

- no safety, request-budget, or evidence-overwrite violations;
- schema-valid artifacts and reproducible detector versions;
- stable results on repeat scans or a documented temporal estimand;
- missingness reported by sampling stratum and source; and
- sensitivity analyses for signal weights, coverage thresholds, and disputed classifications.

Until these gates pass, publish evidence coverage and individual observations rather than a ranked
index.
