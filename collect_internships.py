#!/usr/bin/env python3
"""Collect live internship listings from LinkedIn search and public career pages."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from internship_collectors.runner import collect_all_sources


DEFAULT_CONFIG_PATH = Path("data/source_config.example.json")
DEFAULT_OUTPUT_DIR = Path("data/live_sources")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect live internship listings from LinkedIn guest search, Greenhouse, "
            "Lever, and configured career pages."
        ),
    )
    parser.add_argument(
        "--config-path",
        default=os.getenv("INTERNSHIP_COLLECTOR_CONFIG", str(DEFAULT_CONFIG_PATH)),
        help="JSON config describing live sources to scrape.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("INTERNSHIP_LIVE_SOURCES_DIR", str(DEFAULT_OUTPUT_DIR)),
        help="Directory where per-source JSON feeds are written.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    config_path = Path(args.config_path)
    output_dir = Path(args.output_dir)
    if not config_path.exists():
        print(f"Error: Config file does not exist: {config_path}", file=sys.stderr)
        return 1
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        summary = collect_all_sources(config, output_dir=output_dir)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2))
    if summary.get("errors") and summary.get("total_jobs", 0) == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
