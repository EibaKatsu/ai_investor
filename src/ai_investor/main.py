from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from ai_investor.config import load_strategy
from ai_investor.pipeline import InvestorPipeline
from ai_investor.reporting.markdown_report import write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI investor pipeline")
    parser.add_argument("--config", required=True, help="Path to strategy YAML")
    parser.add_argument("--as-of", dest="as_of", default=date.today().isoformat())
    parser.add_argument("--output", default="reports")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--top-n", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    dotenv_path = Path.cwd() / ".env"
    if dotenv_path.is_file():
        load_dotenv(dotenv_path=dotenv_path, override=False)
        # If an empty env var is already set, prefer non-empty value from .env.
        if not os.getenv("OPENAI_API_KEY", "").strip():
            load_dotenv(dotenv_path=dotenv_path, override=True)
    else:
        load_dotenv(override=False)
    args = parse_args()
    strategy = load_strategy(args.config)
    as_of = date.fromisoformat(args.as_of)

    pipeline = InvestorPipeline(strategy)
    result = pipeline.run(dry_run=args.dry_run, top_n=args.top_n, top_k=args.top_k, as_of=as_of)
    if args.dry_run:
        print(f"[dry-run] Loaded strategy: {strategy.name} (mode={strategy.mode})")
        print(f"[dry-run] Quant metrics: {len(strategy.quantitative.metrics)}")
        print(f"[dry-run] Qual axes: {len(strategy.qualitative.axes)}")
        return 0

    report_path = write_report(result, args.output, as_of)
    print(f"Report generated: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
