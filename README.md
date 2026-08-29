# Web Openness Observatory

The Web Openness Observatory measures how public websites can be accessed by people, conventional crawlers, and software agents. It records technical, policy, economic, and preservation evidence without bypassing access controls. Repeated, versioned measurements can show where access differs and how it changes over time.

**New to the project? Start with [the intern guide](docs/START_HERE.md).** It explains the goal, current system, work plan, and a good first contribution.

## Research questions

- Who can access a public website, under what conditions, and through which interfaces?
- How do access patterns differ across sectors, regions, and popularity bands?
- Which technical, legal, and economic conditions are associated with those differences?
- How does web openness change across repeated measurement waves?

## Current state

The repository contains a working, policy-aware collector and restart-safe local batch runner. The scanner has an operational path for **110 signals** across ten families:

| Family | Signals | Examples |
| --- | ---: | --- |
| Network | 16 | DNS, TLS, HTTP version |
| Infrastructure | 21 | CDN, edge, WAF, cache, hosting hints |
| Crawler | 12 | `robots.txt`, AI-agent rules, crawl delay, HTTP outcomes |
| Browser | 3 | Optional rendered navigation and network summary |
| Human | 17 | Reachability and conservative barrier evidence |
| Metadata | 17 | Sitemaps, JSON-LD, feeds, `llms.txt` |
| Agent | 9 | Candidate OpenAPI, GraphQL, MCP, A2A, and API links |
| Legal | 5 | Policy, license, scraping, and AI-use declarations |
| Economic | 6 | Pricing, registration, subscription, and metering declarations |
| Preservation | 4 | Cache and optional public-archive evidence |

“Operational” means code can collect a result, record no evidence, or explain a skip. It does **not** mean every detector is validated or that all 110 fields should enter an index. See [measurement coverage](docs/measurement_coverage.md) for methods and limits.

The project does not yet publish an openness score. Detector validation, a frozen sampling frame, pilot collection, missingness analysis, and a preregistered scoring method come first.

## Quick start

Requirements: Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups
make check
```

All tests are offline and use deterministic fixtures. After reviewing the scanner policy, collect one live public-domain snapshot:

```bash
uv run web-openness scan example.org --json
```

Snapshots are written under `data/snapshots/<date>/<domain>/` by default.

## Common workflows

Run the small diagnostic canary:

```bash
uv run web-openness smoke \
  --domains-file examples/smoke_domains.txt \
  --cease-list examples/cease_list.txt \
  --concurrency 3
```

Run a restart-safe reviewed batch:

```bash
uv run web-openness batch \
  --domains-file examples/smoke_domains.txt \
  --cease-list examples/cease_list.txt \
  --concurrency 3 \
  --json-progress
```

Create a deterministic sample and export collected snapshots:

```bash
uv run web-openness frame-sample data/frame/pilot.csv \
  --frame-version pilot-v0.1 \
  --code-revision COMMIT_SHA \
  --seed pilot-v0.1 \
  --manifest-output data/research/pilot-v0.1.manifest.json \
  --targets-output data/research/pilot-v0.1.domains.txt

uv run web-openness analyze data/snapshots --output data/analysis
```

Live collection is transparent and bounded. The scanner honors `robots.txt`, rate limits, cease-list entries, authentication boundaries, paywalls, CAPTCHAs, and other standard controls. It never logs in, submits forms, or tries to evade a block. Browser and preservation requests are opt-in; see the [smoke-test guide](docs/smoke_test.md).

## How the code is organized

```text
src/web_openness/
├── probes/          independent measurement families
├── client.py        destination safety, HTTP limits, and request evidence
├── politeness.py    persistent pacing, retries, and temporary cease state
├── models.py        versioned observation and snapshot contracts
├── signals.py       operational signal registry
├── pipeline.py      deterministic probe orchestration
├── runner.py        restart-safe batch coordination
├── frame.py         reproducible sample selection
└── analysis.py      validated CSV/JSON exports
```

Collection, evidence, analysis, and scoring are separate layers. The current system uses files and SQLite on one coordinator; it does not need a queue cluster, Kubernetes, or a web dashboard for the pilot. See [architecture](docs/architecture.md) for the boundaries and scaling rule.

## Documentation

| Read this | For |
| --- | --- |
| [Start here](docs/START_HERE.md) | Project context, plan, and first tasks |
| [Contributing](CONTRIBUTING.md) | Setup, code changes, tests, and pull requests |
| [Measurement coverage](docs/measurement_coverage.md) | Signal families, methods, and limitations |
| [Plot roadmap](docs/plots.md) | Planned diagnostic and research figures |
| [Architecture](docs/architecture.md) | Current data flow and module contracts |
| [Pilot sampling](docs/methodology/pilot_sampling.md) | Population, strata, waves, and quality gates |
| [Analysis](docs/analysis.md) | Selection manifests and exported tables |
| [Scanner policy](docs/scanner.md) | Identity, behavior, corrections, and opt-out |
| [Deployment](docs/deployment.md) | Safe worker and network setup |
| [Operations](docs/operations.md) | Start, inspect, stop, and resume a batch |
| [Scoring draft](docs/methodology/scoring.md) | Preregistration principles; not a leaderboard |

## Research and engineering rules

- Measure barriers; never defeat them.
- Keep requests few, slow, identifiable, and auditable.
- Treat `no_evidence`, `skipped`, and `error` as different outcomes; none means `false`.
- Keep raw evidence immutable and derived classifications reproducible.
- Validate a detector before using it in a score.
- Version code, schemas, sampling frames, detector rules, and methods.
- Add infrastructure only after a measured pilot demonstrates the need.

The goal is a defensible longitudinal dataset, not the largest possible crawl.
