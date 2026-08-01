import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path

from web_openness.config import DEFAULT_USER_AGENT, ScanConfig
from web_openness.models import DomainSnapshot
from web_openness.pipeline import Scanner
from web_openness.storage import write_snapshot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="web-openness",
        description="Collect a policy-aware Web Openness Observatory snapshot.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="scan one or more public domains")
    scan.add_argument("targets", nargs="+", help="domains or HTTP(S) origins")
    scan.add_argument(
        "--output",
        type=Path,
        default=Path("data/snapshots"),
        help="snapshot root (default: data/snapshots)",
    )
    scan.add_argument("--json", action="store_true", help="also print snapshots as JSON")
    scan.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    scan.add_argument("--request-budget", type=int, default=8)
    scan.add_argument("--request-delay", type=float, default=1.0)
    scan.add_argument("--timeout", type=float, default=15.0)
    scan.add_argument("--max-response-bytes", type=int, default=1_000_000)
    return parser


async def run_scans(args: argparse.Namespace) -> list[tuple[DomainSnapshot, Path]]:
    config = ScanConfig(
        user_agent=args.user_agent,
        request_budget=args.request_budget,
        request_delay_seconds=args.request_delay,
        timeout_seconds=args.timeout,
        max_response_bytes=args.max_response_bytes,
    )
    scanner = Scanner(config)
    results: list[tuple[DomainSnapshot, Path]] = []
    for target in args.targets:
        snapshot = await scanner.scan(target)
        results.append((snapshot, write_snapshot(snapshot, args.output)))
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        results = asyncio.run(run_scans(args))
    except ValueError as exc:
        parser.error(str(exc))

    for snapshot, path in results:
        print(f"{snapshot.domain}: {path}")
        if args.json:
            print(snapshot.model_dump_json(indent=2))
    return 0
