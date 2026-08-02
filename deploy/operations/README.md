# Pilot operations

This is the minimum provider-neutral gate before a live pilot. It uses the existing SQLite runner,
JSON progress output, cease list, and global-stop commands. It does not require a scheduler,
Kubernetes, or a cloud control plane.

## Prepare identity and complaint handling

1. Copy `deploy/scanner-site/index.html.example` to the scanner site's `index.html` and replace every
   `REPLACE_` value.
2. Copy `deploy/scanner-site/.well-known/probing.txt.example` to
   `.well-known/probing.txt`, replace the examples, and set `Expires` to less than one year ahead.
3. Create an empty, access-controlled JSON Lines complaint log. Records use only `domain`, `scope`,
   `received_at`, `status`, and an internal `reference`; do not put message bodies or unnecessary
   personal data in it. The example is a format illustration, not a real complaint.
4. Ensure the published contact reaches a monitored group, and assign a human primary and backup
   operator for the pilot window.

Run the local, read-only readiness check against rendered deployment files and an initialized runner
database:

```bash
uv run python deploy/check_readiness.py \
  --site-dir /srv/scanner-site \
  --cease-list /srv/web-openness/cease-list.txt \
  --state /srv/web-openness/runner.sqlite3 \
  --complaint-log /srv/web-openness/complaints.jsonl
```

After publishing, fetch the scanner page and `/.well-known/probing.txt` from outside the worker and
verify HTTPS status, content type, contact, source addresses, reverse DNS, and expiry. The local
check intentionally makes no network requests.

## Monitor one pilot run

Retain the batch run ID and JSON progress in the operator's normal log sink:

```bash
uv run web-openness batch \
  --domains-file reviewed-pilot.txt \
  --concurrency 3 \
  --json-progress

uv run web-openness batch-status RUN_ID --state /srv/web-openness/runner.sqlite3
```

Alert a human and stop expansion when failures, deferrals, robots denials, HTTP 403/429 responses,
browser crashes, per-domain request counts, or complaint volume exceed the pilot's pre-registered
limits. The collector emits the raw counts; thresholds belong in the study protocol and the
operator's existing monitor rather than in provider-specific code here.

## Exercise stop controls before the pilot

Use a disposable initialized state database. Set the database-wide stop, confirm a pending test run
starts no work, then clear it only after recording the drill:

```bash
uv run web-openness batch-stop-all --state /tmp/web-openness-stop-drill.sqlite3
uv run web-openness batch-status RUN_ID --state /tmp/web-openness-stop-drill.sqlite3
uv run web-openness batch-clear-stop --state /tmp/web-openness-stop-drill.sqlite3
```

During a real complaint or unexpected-load event, run `batch-stop-all` against the production state
database first. Record the run ID, time, affected domain, complaint reference, and operator action.
Add an accepted domain to the cease list before clearing the stop. In-flight domain scans finish;
the global stop prevents new jobs from starting.
