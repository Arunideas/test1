#!/usr/bin/env python3
"""Collect verified internships from multiple sources and publish daily intelligence.

This agent is separate from the employability content engine. It aggregates jobs
from JSON source files or directories, formats a daily briefing, and can post
the update to LinkedIn.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from linkedin_company_page_agent import LinkedInCompanyPageAgent, LinkedInPostError
from weekly_linkedin_series import INTERNSHIP_SERIES, SERIES_HASHTAGS, prepend_series_header, resolve_series_for_date


DEFAULT_SOURCES_PATH = Path("data/sample_sources")
DEFAULT_HISTORY_PATH = Path("daily_internship_history.json")
DEFAULT_OUTPUT_DIR = Path("daily_internship_output")
DEFAULT_MAX_LINKEDIN_CHARS = 3000
DEFAULT_MAX_INTERNSHIP_HASHTAGS = 12
DEFAULT_CATEGORY_ORDER = (
    "Software Engineering",
    "Digital Marketing",
    "Data Analytics",
    "HR",
    "Finance",
    "Operations",
    "Design",
    "Sales",
    "Other",
)
WORK_MODES = frozenset({"Remote", "Hybrid", "Onsite"})

INTERNSHIP_BASE_HASHTAGS = (
    "WorldOfInterns",
    "InternshipOpportunities",
    "Internships",
    "VerifiedInternships",
    "StudentJobs",
    "HiringNow",
)

INTERNSHIP_CATEGORY_HASHTAGS: dict[str, tuple[str, ...]] = {
    "Software Engineering": ("SoftwareInternship", "TechInternship", "DeveloperJobs"),
    "Digital Marketing": ("MarketingInternship", "DigitalMarketing", "GrowthMarketing"),
    "Data Analytics": ("DataAnalytics", "AnalyticsInternship", "DataInternship"),
    "HR": ("HRInternship", "PeopleOps", "TalentTeam"),
    "Finance": ("FinanceInternship", "FinanceCareers", "AccountingInternship"),
    "Operations": ("OperationsInternship", "OpsCareers", "BusinessOperations"),
    "Design": ("DesignInternship", "UXDesign", "CreativeCareers"),
    "Sales": ("SalesInternship", "BusinessDevelopment", "SalesCareers"),
    "Other": ("EarlyCareer", "CareerLaunch"),
}

WORK_MODE_HASHTAGS: dict[str, tuple[str, ...]] = {
    "Remote": ("RemoteInternship", "WorkFromHome"),
    "Hybrid": ("HybridWork", "FlexibleInternship"),
    "Onsite": ("OnsiteInternship", "OfficeInternship"),
}

INDIA_LOCATION_MARKERS = (
    "india",
    "bangalore",
    "bengaluru",
    "mumbai",
    "delhi",
    "hyderabad",
    "pune",
    "chennai",
    "gurgaon",
    "gurugram",
    "noida",
    "kolkata",
    "remote india",
)

ROLE_KEYWORD_HASHTAGS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("software", "backend", "frontend", "full stack", "developer", "engineering"), "SoftwareInternship"),
    (("devops", "qa", "mobile"), "TechInternship"),
    (("marketing", "seo", "social media", "content", "brand"), "MarketingInternship"),
    (("data", "analytics", "analyst", "power bi", "sql"), "DataAnalytics"),
    (("design", "ux", "ui", "creative"), "DesignInternship"),
    (("finance", "accounting"), "FinanceInternship"),
    (("human resources", " hr ", "people ops"), "HRInternship"),
    (("sales", "business development"), "SalesInternship"),
    (("operations", "ops"), "OperationsInternship"),
)


@dataclass(frozen=True)
class InternshipJob:
    job_id: str
    company: str
    role: str
    category: str
    location: str
    stipend: str
    work_mode: str
    duration: str
    apply_link: str
    last_date: str
    verified: bool
    source: str
    collected_at: str
    verification_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "company": self.company,
            "role": self.role,
            "category": self.category,
            "location": self.location,
            "stipend": self.stipend,
            "work_mode": self.work_mode,
            "duration": self.duration,
            "apply_link": self.apply_link,
            "last_date": self.last_date,
            "verified": self.verified,
            "source": self.source,
            "collected_at": self.collected_at,
            "verification_notes": self.verification_notes,
        }


@dataclass
class DailyInternshipBrief:
    report_date: dt.date
    jobs: list[InternshipJob]
    sources: list[str] = field(default_factory=list)
    truncated: bool = False
    omitted_job_count: int = 0

    @property
    def total_count(self) -> int:
        return len(self.jobs)

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for job in self.jobs:
            counts[job.category] += 1
        return dict(counts)

    def jobs_by_category(self) -> dict[str, list[InternshipJob]]:
        grouped: dict[str, list[InternshipJob]] = defaultdict(list)
        for job in self.jobs:
            grouped[job.category].append(job)
        for category in grouped:
            grouped[category].sort(key=lambda item: (item.company.lower(), item.role.lower()))
        return dict(grouped)


def normalize_work_mode(value: str) -> str:
    cleaned = value.strip()
    aliases = {
        "remote": "Remote",
        "hybrid": "Hybrid",
        "onsite": "Onsite",
        "on-site": "Onsite",
        "on site": "Onsite",
        "office": "Onsite",
        "wfh": "Remote",
    }
    normalized = aliases.get(cleaned.lower(), cleaned)
    if normalized not in WORK_MODES:
        raise ValueError(f"Unsupported work mode: {value!r}. Use Remote, Hybrid, or Onsite.")
    return normalized


def normalize_category(value: str) -> str:
    cleaned = value.strip()
    aliases = {
        "software": "Software Engineering",
        "software engineering": "Software Engineering",
        "engineering": "Software Engineering",
        "marketing": "Digital Marketing",
        "digital marketing": "Digital Marketing",
        "data analytics": "Data Analytics",
        "analytics": "Data Analytics",
        "human resources": "HR",
        "hr": "HR",
        "finance": "Finance",
        "operations": "Operations",
        "design": "Design",
        "sales": "Sales",
    }
    return aliases.get(cleaned.lower(), cleaned or "Other")


def job_fingerprint(company: str, role: str, apply_link: str) -> str:
    raw = f"{company.strip().lower()}|{role.strip().lower()}|{apply_link.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_job_id(company: str, role: str, apply_link: str) -> str:
    return job_fingerprint(company, role, apply_link)[:16]


def parse_job(raw: dict[str, Any], *, source: str, collected_at: str) -> InternshipJob:
    required = (
        "company",
        "role",
        "category",
        "location",
        "stipend",
        "work_mode",
        "duration",
        "apply_link",
        "last_date",
    )
    missing = [key for key in required if not str(raw.get(key, "")).strip()]
    if missing:
        raise ValueError(f"Job from {source} is missing required fields: {', '.join(missing)}")

    company = str(raw["company"]).strip()
    role = str(raw["role"]).strip()
    apply_link = str(raw["apply_link"]).strip()
    if not apply_link.startswith(("http://", "https://")):
        raise ValueError(f"Job {company} / {role} has an invalid apply_link.")

    verified = bool(raw.get("verified", False))
    return InternshipJob(
        job_id=str(raw.get("id") or build_job_id(company, role, apply_link)),
        company=company,
        role=role,
        category=normalize_category(str(raw["category"])),
        location=str(raw["location"]).strip(),
        stipend=str(raw["stipend"]).strip(),
        work_mode=normalize_work_mode(str(raw["work_mode"])),
        duration=str(raw["duration"]).strip(),
        apply_link=apply_link,
        last_date=str(raw["last_date"]).strip(),
        verified=verified,
        source=source,
        collected_at=collected_at,
        verification_notes=str(raw.get("verification_notes", "")).strip(),
    )


def load_jobs_from_file(path: Path) -> list[InternshipJob]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        source = path.stem
        collected_at = dt.datetime.now(dt.timezone.utc).isoformat()
        raw_jobs = payload
    elif isinstance(payload, dict):
        source = str(payload.get("source") or path.stem)
        collected_at = str(payload.get("collected_at") or dt.datetime.now(dt.timezone.utc).isoformat())
        raw_jobs = payload.get("jobs", [])
    else:
        raise ValueError(f"Unsupported JSON structure in {path}")

    if not isinstance(raw_jobs, list):
        raise ValueError(f"Expected a list of jobs in {path}")

    jobs: list[InternshipJob] = []
    for index, raw in enumerate(raw_jobs):
        if not isinstance(raw, dict):
            raise ValueError(f"Job entry #{index + 1} in {path} must be an object.")
        jobs.append(parse_job(raw, source=source, collected_at=collected_at))
    return jobs


def collect_jobs_from_sources(
    sources_path: Path,
    *,
    verified_only: bool = True,
) -> tuple[list[InternshipJob], list[str]]:
    if not sources_path.exists():
        raise FileNotFoundError(f"Sources path does not exist: {sources_path}")

    files: list[Path]
    if sources_path.is_dir():
        files = sorted(
            path
            for path in sources_path.glob("*.json")
            if path.is_file() and path.name not in {"collection_summary.json"}
        )
        if not files:
            raise ValueError(f"No JSON source files found in {sources_path}")
    else:
        files = [sources_path]

    merged: dict[str, InternshipJob] = {}
    source_names: list[str] = []
    for file_path in files:
        for job in load_jobs_from_file(file_path):
            if verified_only and not job.verified:
                continue
            fingerprint = job_fingerprint(job.company, job.role, job.apply_link)
            merged[fingerprint] = job
        source_names.append(file_path.name)

    jobs = sorted(
        merged.values(),
        key=lambda item: (
            DEFAULT_CATEGORY_ORDER.index(item.category)
            if item.category in DEFAULT_CATEGORY_ORDER
            else len(DEFAULT_CATEGORY_ORDER),
            item.category.lower(),
            item.company.lower(),
            item.role.lower(),
        ),
    )
    return jobs, source_names


def load_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"posted_reports": [], "posted_job_ids": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("posted_reports", [])
    data.setdefault("posted_job_ids", [])
    return data


def save_history(path: Path, history: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def report_hash(report_date: dt.date, job_ids: Iterable[str]) -> str:
    payload = f"{report_date.isoformat()}|" + "|".join(sorted(job_ids))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_hashtag(tag: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "", tag.strip().lstrip("#"))
    return cleaned


def format_hashtag(tag: str) -> str:
    normalized = normalize_hashtag(tag)
    return f"#{normalized}" if normalized else ""


def extract_hashtags(text: str) -> set[str]:
    return {
        normalize_hashtag(match)
        for match in re.findall(r"#(\w+)", text)
        if normalize_hashtag(match)
    }


def extract_hashtags_from_jobs(brief: DailyInternshipBrief, *, max_tags: int = 4) -> list[str]:
    combined = " ".join(f"{job.role} {job.category}" for job in brief.jobs).lower()
    tags: list[str] = []
    seen: set[str] = set()
    for keywords, tag in ROLE_KEYWORD_HASHTAGS:
        if len(tags) >= max_tags:
            break
        if not any(keyword in combined for keyword in keywords):
            continue
        normalized = normalize_hashtag(tag)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        tags.append(normalized)
    return tags


def build_internship_hashtags(brief: DailyInternshipBrief, *, max_tags: int = DEFAULT_MAX_INTERNSHIP_HASHTAGS) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()

    def add(*candidates: str) -> None:
        for candidate in candidates:
            if len(tags) >= max_tags:
                return
            normalized = normalize_hashtag(candidate)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            tags.append(normalized)

    add(*INTERNSHIP_BASE_HASHTAGS[:3])
    add(*SERIES_HASHTAGS.get(INTERNSHIP_SERIES.key, ()))
    add(*extract_hashtags_from_jobs(brief))

    counts = brief.category_counts()
    top_categories = sorted(counts, key=lambda category: (-counts[category], category))
    for category in top_categories[:3]:
        add(*INTERNSHIP_CATEGORY_HASHTAGS.get(category, ()))

    work_mode_counts: dict[str, int] = defaultdict(int)
    for job in brief.jobs:
        work_mode_counts[job.work_mode] += 1
    for work_mode, _ in sorted(work_mode_counts.items(), key=lambda item: (-item[1], item[0]))[:2]:
        add(*WORK_MODE_HASHTAGS.get(work_mode, ()))

    locations = " ".join(job.location.lower() for job in brief.jobs)
    if any(marker in locations for marker in INDIA_LOCATION_MARKERS):
        add("IndiaJobs", "IndiaInternships")

    return tags[:max_tags]


def append_hashtags_to_post(
    text: str,
    hashtags: list[str],
    *,
    max_chars: int | None = None,
) -> tuple[str, list[str]]:
    body = text.strip()
    if not body or not hashtags:
        return body, hashtags

    existing = extract_hashtags(body)
    missing = [tag for tag in hashtags if normalize_hashtag(tag) not in existing]
    if not missing and existing:
        return body, hashtags

    hashtag_line = " ".join(format_hashtag(tag) for tag in (missing or hashtags))
    hashtag_block = f"\n\n{hashtag_line}"
    if max_chars is None:
        return f"{body}{hashtag_block}", hashtags

    allowed_body_len = max_chars - len(hashtag_block)
    if allowed_body_len < 1:
        return body[:max_chars], hashtags
    if len(body) > allowed_body_len:
        body = body[: allowed_body_len - 3].rstrip() + "..."
    return f"{body}{hashtag_block}", hashtags


def format_summary_header(brief: DailyInternshipBrief) -> str:
    lines = [
        f"🔥 Today's Verified Internship Opportunities ({brief.total_count})",
        "",
    ]
    counts = brief.category_counts()
    ordered_categories = [
        category
        for category in DEFAULT_CATEGORY_ORDER
        if category in counts
    ] + sorted(category for category in counts if category not in DEFAULT_CATEGORY_ORDER)
    for category in ordered_categories:
        lines.extend(
            [
                f"📍 {category}",
                f"{counts[category]} Opening{'s' if counts[category] != 1 else ''}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def format_job_block(job: InternshipJob, *, index: int | None = None) -> str:
    prefix = f"{index}. " if index is not None else ""
    verified_line = "Verified ✅" if job.verified else "Proceed with Caution ⚠️"
    lines = [
        f"{prefix}{job.company} — {job.role}",
        f"Location: {job.location}",
        f"Stipend: {job.stipend}",
        f"Mode: {job.work_mode}",
        f"Duration: {job.duration}",
        f"Apply: {job.apply_link}",
        f"Last Date: {job.last_date}",
        verified_line,
    ]
    return "\n".join(lines)


def format_category_section(category: str, jobs: list[InternshipJob]) -> str:
    lines = [category, ""]
    for index, job in enumerate(jobs, start=1):
        lines.append(format_job_block(job, index=index))
        lines.append("")
    return "\n".join(lines).rstrip()


def format_daily_brief_text(
    brief: DailyInternshipBrief,
    *,
    max_chars: int = DEFAULT_MAX_LINKEDIN_CHARS,
    continue_url: str | None = None,
) -> str:
    summary = format_summary_header(brief)
    grouped = brief.jobs_by_category()
    ordered_categories = [
        category
        for category in DEFAULT_CATEGORY_ORDER
        if category in grouped
    ] + sorted(category for category in grouped if category not in DEFAULT_CATEGORY_ORDER)

    sections: list[str] = [summary, "", "—", ""]
    included_jobs: list[InternshipJob] = []

    for category in ordered_categories:
        category_jobs = grouped[category]
        candidate_section = format_category_section(category, category_jobs)
        candidate_text = "\n\n".join(sections + [candidate_section]).strip()
        if len(candidate_text) <= max_chars:
            sections.append(candidate_section)
            sections.append("")
            included_jobs.extend(category_jobs)
            continue

        remaining_chars = max_chars - len("\n\n".join(sections).strip()) - 2
        partial_jobs: list[InternshipJob] = []
        partial_lines = [category, ""]
        for index, job in enumerate(category_jobs, start=1):
            block = format_job_block(job, index=index)
            candidate = "\n".join(partial_lines + [block, ""]).strip()
            if len(candidate) > remaining_chars:
                break
            partial_lines.extend([block, ""])
            partial_jobs.append(job)

        if partial_jobs:
            sections.append("\n".join(partial_lines).rstrip())
            sections.append("")
            included_jobs.extend(partial_jobs)

        brief.truncated = len(included_jobs) < brief.total_count
        brief.omitted_job_count = brief.total_count - len(included_jobs)
        break

    text = "\n\n".join(section for section in sections if section).strip()
    if brief.truncated:
        footer_parts = [
            f"+{brief.omitted_job_count} more verified openings not shown here due to LinkedIn length limits."
        ]
        if continue_url:
            footer_parts.append(f"Full list: {continue_url}")
        text = f"{text}\n\n" + "\n".join(footer_parts)
        if len(text) > max_chars:
            text = text[: max_chars - 3].rstrip() + "..."
    return text


def build_daily_brief(
    *,
    report_date: dt.date | None = None,
    sources_path: Path,
    verified_only: bool = True,
    max_chars: int = DEFAULT_MAX_LINKEDIN_CHARS,
    continue_url: str | None = None,
) -> DailyInternshipBrief:
    jobs, source_names = collect_jobs_from_sources(sources_path, verified_only=verified_only)
    brief = DailyInternshipBrief(
        report_date=report_date or dt.date.today(),
        jobs=jobs,
        sources=source_names,
    )
    format_daily_brief_text(brief, max_chars=max_chars, continue_url=continue_url)
    return brief


def save_brief_artifacts(
    brief: DailyInternshipBrief,
    output_dir: Path,
    text: str,
    *,
    hashtags: list[str] | None = None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    date_prefix = brief.report_date.isoformat()
    text_path = output_dir / f"{date_prefix}-daily-internship-intelligence.txt"
    json_path = output_dir / f"{date_prefix}-daily-internship-intelligence.json"

    text_path.write_text(text + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "report_date": brief.report_date.isoformat(),
                "total_count": brief.total_count,
                "category_counts": brief.category_counts(),
                "sources": brief.sources,
                "truncated": brief.truncated,
                "omitted_job_count": brief.omitted_job_count,
                "jobs": [job.to_dict() for job in brief.jobs],
                "linkedin_text": text,
                "hashtags": hashtags or extract_hashtags(text),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {"text_path": str(text_path), "json_path": str(json_path)}


def record_report(
    history: dict[str, Any],
    brief: DailyInternshipBrief,
    *,
    text: str,
    artifact_paths: dict[str, str],
    post_result: dict[str, Any] | None,
    dry_run: bool,
) -> None:
    content_hash = report_hash(brief.report_date, [job.job_id for job in brief.jobs])
    entry = {
        "report_date": brief.report_date.isoformat(),
        "report_hash": content_hash,
        "total_count": brief.total_count,
        "category_counts": brief.category_counts(),
        "sources": brief.sources,
        "truncated": brief.truncated,
        "omitted_job_count": brief.omitted_job_count,
        "job_ids": [job.job_id for job in brief.jobs],
        "text_path": artifact_paths.get("text_path"),
        "json_path": artifact_paths.get("json_path"),
        "posted_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "dry_run": dry_run,
        "post_response": post_result,
        "preview": text[:500],
    }
    history.setdefault("posted_reports", []).append(entry)
    if not dry_run:
        history.setdefault("posted_job_ids", [])
        for job in brief.jobs:
            if job.job_id not in history["posted_job_ids"]:
                history["posted_job_ids"].append(job.job_id)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and optionally post Daily Internship Intelligence from multiple JSON sources.",
    )
    parser.add_argument(
        "--sources-path",
        default=os.getenv("INTERNSHIP_SOURCES_PATH", str(DEFAULT_SOURCES_PATH)),
        help="Directory of JSON source files or a single JSON source file.",
    )
    parser.add_argument(
        "--history-path",
        default=os.getenv("INTERNSHIP_HISTORY_PATH", str(DEFAULT_HISTORY_PATH)),
        help="JSON file used to track posted daily internship reports.",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("INTERNSHIP_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)),
        help="Directory for generated daily internship intelligence artifacts.",
    )
    parser.add_argument(
        "--report-date",
        help="Optional report date (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=int(os.getenv("INTERNSHIP_MAX_LINKEDIN_CHARS", DEFAULT_MAX_LINKEDIN_CHARS)),
        help="Maximum LinkedIn post length. Defaults to 3000.",
    )
    parser.add_argument(
        "--continue-url",
        default=os.getenv("INTERNSHIP_CONTINUE_URL"),
        help="Optional URL shown when the post is truncated for LinkedIn length limits.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Post only the category summary block without individual job listings.",
    )
    parser.add_argument(
        "--include-unverified",
        action="store_true",
        help="Include jobs that are not marked verified.",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Publish the daily internship intelligence update to LinkedIn.",
    )
    parser.add_argument(
        "--record-dry-run",
        action="store_true",
        help="Write dry-run output to history without treating it as a live post.",
    )
    parser.add_argument(
        "--skip-unless-wednesday",
        action="store_true",
        help="Skip generation unless today is Wednesday's Internship Opportunities series.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even when today is not Wednesday.",
    )
    parser.add_argument(
        "--post-as",
        choices=("member", "organization"),
        default=os.getenv("LINKEDIN_POST_AS", "member"),
        help="LinkedIn author type. Defaults to member for personal posting.",
    )
    parser.add_argument(
        "--access-token",
        default=os.getenv("LINKEDIN_ACCESS_TOKEN"),
        help="LinkedIn access token. Defaults to LINKEDIN_ACCESS_TOKEN.",
    )
    parser.add_argument(
        "--member-id",
        default=os.getenv("LINKEDIN_MEMBER_ID"),
        help="LinkedIn member id for personal posts.",
    )
    parser.add_argument(
        "--organization-id",
        default=os.getenv("LINKEDIN_ORGANIZATION_ID"),
        help="LinkedIn organization id for company page posts.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    sources_path = Path(args.sources_path)
    history_path = Path(args.history_path)
    output_dir = Path(args.output_dir)
    report_date = dt.date.fromisoformat(args.report_date) if args.report_date else dt.date.today()
    series = resolve_series_for_date(report_date)

    if args.skip_unless_wednesday and series.key != "internship_opportunities" and not args.force:
        print(
            json.dumps(
                {
                    "dry_run": not args.post,
                    "skipped": True,
                    "report_date": report_date.isoformat(),
                    "series_key": series.key,
                    "series_label": series.label,
                    "reason": (
                        "Internship Opportunities runs on Wednesday. "
                        "Run daily_story_linkedin_agent.py on other days."
                    ),
                },
                indent=2,
            )
        )
        return 0

    try:
        brief = build_daily_brief(
            report_date=report_date,
            sources_path=sources_path,
            verified_only=not args.include_unverified,
            max_chars=args.max_chars,
            continue_url=args.continue_url,
        )
        if not brief.jobs:
            raise ValueError("No verified internship jobs were collected from the configured sources.")
        if args.summary_only:
            text = format_summary_header(brief)
            brief.truncated = True
            brief.omitted_job_count = brief.total_count
            if args.continue_url:
                text = f"{text}\n\nFull verified list: {args.continue_url}"
        else:
            text = format_daily_brief_text(
                brief,
                max_chars=args.max_chars,
                continue_url=args.continue_url,
            )
        text = prepend_series_header(text, INTERNSHIP_SERIES)
        hashtags = build_internship_hashtags(brief)
        text, hashtags = append_hashtags_to_post(
            text,
            hashtags,
            max_chars=args.max_chars,
        )
        artifacts = save_brief_artifacts(brief, output_dir, text, hashtags=hashtags)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    post_result: dict[str, Any] | None = None
    if args.post:
        agent = LinkedInCompanyPageAgent(
            organization_urn=(
                f"urn:li:organization:{args.organization_id}"
                if args.organization_id
                else "urn:li:organization:YOUR_ORGANIZATION_ID"
            ),
            member_urn=f"urn:li:person:{args.member_id}" if args.member_id else None,
            access_token=args.access_token,
        )
        try:
            post_result = agent.post_text(text, dry_run=False, post_as=args.post_as)
        except (LinkedInPostError, ValueError) as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

    if args.post or args.record_dry_run:
        history = load_history(history_path)
        record_report(
            history,
            brief,
            text=text,
            artifact_paths=artifacts,
            post_result=post_result,
            dry_run=not args.post,
        )
        try:
            save_history(history_path, history)
        except OSError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

    response = {
        "dry_run": not args.post,
        "report_date": brief.report_date.isoformat(),
        "series_key": INTERNSHIP_SERIES.key,
        "series_label": INTERNSHIP_SERIES.label,
        "total_count": brief.total_count,
        "category_counts": brief.category_counts(),
        "sources": brief.sources,
        "truncated": brief.truncated,
        "omitted_job_count": brief.omitted_job_count,
        "text_path": artifacts["text_path"],
        "json_path": artifacts["json_path"],
        "history_path": str(history_path),
        "recorded": args.post or args.record_dry_run,
        "hashtags": hashtags,
        "content": text,
        "post_response": post_result,
    }
    print(json.dumps(response, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
