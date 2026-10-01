#!/usr/bin/env python3
"""Create an Excel workbook grouped by scan run.

Usage:
    python observations_to_excel_full.py data/analysis/observations.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Path to observations.csv")
    parser.add_argument(
        "-o",
        "--output",
     type=Path,
        default=Path("observations_by_run.xlsx"),
    )
    args = parser.parse_args()

    observations = pd.read_csv(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        overview = (
            observations.groupby("run_id", as_index=False)
            .agg(
                domain=("domain", "first"),
                completed_at=("completed_at", "first"),
                observation_count=("signal", "count"),
            )
        )
        overview.to_excel(writer, sheet_name="Overview", index=False)

        for number, (run_id, group) in enumerate(
            observations.groupby("run_id", sort=False), start=1
        ):
            sheet_name = f"Run {number:02d}"
            group.to_excel(writer, sheet_name=sheet_name, index=False)

        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column in worksheet.columns:
                width = min(
                    max(len(str(cell.value or "")) for cell in column) + 2,
                    45,
                )
                worksheet.column_dimensions[column[0].column_letter].width = width

    print(f"Wrote {len(observations)} observations to {args.output}")


if __name__ == "__main__":
    main()