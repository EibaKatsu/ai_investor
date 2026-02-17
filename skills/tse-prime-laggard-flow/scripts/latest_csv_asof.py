#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

DATE_PATTERNS = (
    re.compile(r"(20\d{2})(\d{2})(\d{2})"),
    re.compile(r"(20\d{2})-(\d{2})-(\d{2})"),
)


def _extract_date_from_name(path: Path) -> date | None:
    name = path.name
    for pattern in DATE_PATTERNS:
        match = pattern.search(name)
        if not match:
            continue
        y, m, d = match.groups()
        try:
            return date(int(y), int(m), int(d))
        except ValueError:
            return None
    return None


def resolve_as_of(data_dir: Path) -> tuple[date, Path]:
    csv_files = sorted(p for p in data_dir.rglob("*.csv") if p.is_file())
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found under: {data_dir}")

    dated_files: list[tuple[date, float, Path]] = []
    undated_files: list[tuple[float, Path]] = []

    for csv_path in csv_files:
        stat = csv_path.stat()
        name_date = _extract_date_from_name(csv_path)
        if name_date is not None:
            dated_files.append((name_date, stat.st_mtime, csv_path))
        else:
            undated_files.append((stat.st_mtime, csv_path))

    if dated_files:
        dated_files.sort(key=lambda x: (x[0], x[1], x[2].as_posix()))
        best = dated_files[-1]
        return best[0], best[2]

    undated_files.sort(key=lambda x: (x[0], x[1].as_posix()))
    latest = undated_files[-1]
    as_of = datetime.fromtimestamp(latest[0]).date()
    return as_of, latest[1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve as-of date from the latest CSV under a data directory.",
    )
    parser.add_argument("--data-dir", default="data", help="Data root directory")
    parser.add_argument(
        "--print-path",
        action="store_true",
        help="Print CSV path used for as-of to stderr",
    )
    args = parser.parse_args()

    as_of, csv_path = resolve_as_of(Path(args.data_dir))
    if args.print_path:
        print(f"[as-of-source] {csv_path}", file=sys.stderr, flush=True)
    print(as_of.isoformat())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
