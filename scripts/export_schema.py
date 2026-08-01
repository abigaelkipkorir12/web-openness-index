import argparse
import json
from pathlib import Path

from web_openness.schema import SCHEMA_FILENAME, domain_snapshot_json_schema

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "schemas" / SCHEMA_FILENAME


def render_schema() -> str:
    return f"{json.dumps(domain_snapshot_json_schema(), indent=2, sort_keys=True)}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the versioned domain snapshot schema.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the committed schema does not match the Pydantic model",
    )
    args = parser.parse_args()
    expected = render_schema()

    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != expected:
            parser.error(f"schema is out of date: {args.output}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
