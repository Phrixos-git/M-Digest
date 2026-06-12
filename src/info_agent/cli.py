from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .collector import DailyCollector


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect RSS/Atom entries and write a Markdown daily report.")
    parser.add_argument("--config", default="config/sources.yaml", help="Path to sources.yaml")
    parser.add_argument("--output-dir", default="outputs/daily", help="Directory for daily Markdown reports")
    parser.add_argument("--state", default="outputs/state/seen.json", help="Path to dedupe state JSON")
    parser.add_argument("--date", default=date.today().isoformat(), help="Report date in YYYY-MM-DD")
    parser.add_argument("--limit-per-source", type=int, default=5, help="Maximum entries per source")
    parser.add_argument("--include-seen", action="store_true", help="Include previously seen entries in the report")
    args = parser.parse_args()

    collector = DailyCollector(
        config_path=Path(args.config),
        output_dir=Path(args.output_dir),
        state_path=Path(args.state),
        report_date=args.date,
        limit_per_source=args.limit_per_source,
        include_seen=args.include_seen,
    )
    report_path = collector.run()
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
