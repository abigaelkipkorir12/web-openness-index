# Pilot analysis workflow

The first analysis layer deliberately uses validated CSV and JSON rather than a database service.
It is enough to audit missingness, compare repeated scans, and load the results into DuckDB, R, or
Python without coupling collection to an analysis stack.

## Reproducible sample

Prepare a UTF-8 CSV with the exact columns in
[`examples/pilot_frame.example.csv`](../examples/pilot_frame.example.csv), then freeze a seeded
selection:

```bash
uv run web-openness frame-sample data/frame/pilot-v0.1.csv \
  --frame-version pilot-v0.1 \
  --code-revision COMMIT_SHA \
  --seed pilot-v0.1-2026-08 \
  --per-stratum 4 \
  --manifest-output data/research/pilot-v0.1.manifest.json \
  --targets-output data/research/pilot-v0.1.domains.txt
```

Selection orders each eligible registrable domain by a SHA-256 key derived from the published seed.
It therefore does not depend on Python's random-number implementation or input row order. Duplicate
source memberships are merged only when their classification and eligibility fields agree. The
manifest records the input checksum, source memberships, stratum sizes, selection order, and
inclusion probabilities.

The checked-in frame is illustrative and is not a research sample.

## Snapshot exports

Export a directory containing only schema-valid domain snapshots:

```bash
uv run web-openness analyze data/snapshots --output data/analysis
```

This writes:

- `runs.csv`: one row per scan with request, outcome, and error counts;
- `observations.csv`: one row per domain-signal result, retaining outcome separately from value;
- `changes.csv`: the latest two scans per repeated domain and whether each shared signal changed;
- `summary.json`: aggregate outcome, signal, and longitudinal counts.

The exporter validates current snapshots and explicitly migrates retained schema `0.1.0` confidence
states into the `0.2.0` outcome field. Other malformed or mixed JSON fails the export rather than
being silently dropped. The exporter does not calculate index weights or turn missing values into
negative findings.

DuckDB can query the exports without an import process:

```sql
SELECT signal, outcome, count(*) AS n
FROM read_csv_auto('data/analysis/observations.csv', header = true)
GROUP BY signal, outcome
ORDER BY signal, outcome;
```

Convert a table to Parquet only when dataset size or downstream tooling warrants it:

```sql
COPY (
  SELECT * FROM read_csv_auto('data/analysis/observations.csv', header = true)
) TO 'data/analysis/observations.parquet' (FORMAT PARQUET);
```

Keep raw snapshots immutable. Regenerate derived exports when analysis code changes, and record the
collector revision, frame manifest, analysis revision, and exact command in each release manifest.
