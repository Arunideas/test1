#!/usr/bin/env python3
"""Route daily LinkedIn automation to the correct recurring weekly series."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys

from weekly_linkedin_series import resolve_series_for_date


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the correct World of Interns LinkedIn agent for today's weekly series.",
    )
    parser.add_argument(
        "--date",
        help="Optional date override (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Publish to LinkedIn instead of dry-run generation.",
    )
    parser.add_argument(
        "--record-dry-run",
        action="store_true",
        help="Write dry-run output to history without treating it as a live post.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run the selected agent even when it is not that series day.",
    )
    return parser.parse_args(argv)


def build_command(
    series_key: str,
    *,
    post: bool,
    record_dry_run: bool,
    force: bool,
    report_date: dt.date,
) -> list[str]:
    common_flags: list[str] = []
    if post:
        common_flags.append("--post")
    if record_dry_run:
        common_flags.append("--record-dry-run")
    if force:
        common_flags.append("--force")

    if series_key == "internship_opportunities":
        command = ["python3", "daily_internship_intelligence_agent.py", *common_flags]
        if not force:
            command.append("--skip-unless-wednesday")
        command.extend(["--report-date", report_date.isoformat()])
        return command

    command = [
        "python3",
        "daily_story_linkedin_agent.py",
        *common_flags,
        "--date",
        report_date.isoformat(),
    ]
    return command


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report_date = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    series = resolve_series_for_date(report_date)
    command = build_command(
        series.key,
        post=args.post,
        record_dry_run=args.record_dry_run,
        force=args.force,
        report_date=report_date,
    )

    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        return completed.returncode

    print(
        json.dumps(
            {
                "scheduled_series_key": series.key,
                "scheduled_series_label": series.label,
                "report_date": report_date.isoformat(),
                "command": command,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
