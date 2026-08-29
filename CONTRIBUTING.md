# Contributing

## Set up the project

Install Python 3.12+, [uv](https://docs.astral.sh/uv/), and the development environment:

```bash
git clone https://github.com/shayne-longpre/web-openness-index.git
cd web-openness-index
uv sync --all-groups
make check
```

`make check` runs formatting checks, linting, strict type checking, schema compatibility checks, and the offline test suite.

The optional browser collector needs a separate runtime:

```bash
uv sync --extra browser
uv run playwright install chromium
```

## Make a change

1. Open or choose an issue with one clear outcome.
2. Create a short branch from the current default branch.
3. Add or update deterministic fixtures and tests.
4. Change the smallest module that owns the behavior.
5. Run `make check`.
6. Open a pull request that states the claim, evidence, limitations, and test result.

Keep unrelated cleanup out of a feature pull request. Do not commit generated data, runtime databases, browser binaries, credentials, or live response bodies.

## Change a measurement

Before adding or changing a signal, define:

- the exact claim the signal supports;
- direct evidence versus inferred evidence;
- `observed`, `no_evidence`, `skipped`, and `error` behavior;
- known false positives, false negatives, and ambiguous cases;
- whether collection adds requests or changes policy.

Then:

1. Put collection or parsing in the relevant module under `src/web_openness/probes/`.
2. Use the shared scan context and policy-enforcing client; never create an unbounded side client.
3. Return an `Observation` with method, confidence, outcome, and minimal supporting evidence.
4. Add the key to `src/web_openness/signals.py` only after an operational path exists.
5. Add offline tests for positive, negative, skipped, and malformed inputs where applicable.
6. Update [measurement coverage](docs/measurement_coverage.md) and any affected methodology.
7. Export and commit the JSON Schema only when a snapshot model changes: `make schema`.

Probe code must not calculate index weights. Scoring belongs downstream and requires separate validation.

## Live collection

Tests must not contact live websites. A live canary is an explicit research operation, not a unit test.

Before one, review the [scanner policy](docs/scanner.md), [deployment gate](docs/deployment.md), target list, cease list, request limits, public identity, and stop procedure. Never bypass authentication, CAPTCHAs, paywalls, geographic restrictions, blocks, or `robots.txt` decisions.

## Pull-request checklist

- [ ] The pull request makes one clear research or engineering change.
- [ ] New behavior has deterministic offline tests.
- [ ] `make check` passes.
- [ ] Outcomes distinguish negative evidence, missingness, skips, and errors.
- [ ] Request count, privacy, safety, and longitudinal compatibility are unchanged or documented.
- [ ] Relevant documentation is updated.
