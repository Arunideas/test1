from __future__ import annotations

from typing import Any

from internship_collectors.http_utils import fetch_json
from internship_collectors.utils import (
    infer_category,
    infer_work_mode,
    looks_like_intern,
    normalize_job_payload,
    strip_html,
)


def collect_lever(source: dict[str, Any]) -> list[dict[str, Any]]:
    company = str(source["company"]).strip()
    source_name = str(source.get("source_name") or f"lever_{company}")
    keywords = tuple(source.get("keywords") or ("intern", "internship"))
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    payload = fetch_json(url)
    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected Lever response for company {company!r}.")
    jobs: list[dict[str, Any]] = []
    for item in payload:
        title = str(item.get("text") or item.get("title") or "").strip()
        if not title or not looks_like_intern(title, keywords):
            continue
        location = "Not listed"
        categories = item.get("categories") or {}
        if categories.get("location"):
            location = str(categories["location"])
        elif categories.get("allLocations"):
            location = ", ".join(str(value) for value in categories["allLocations"])
        apply_link = str(item.get("hostedUrl") or item.get("applyUrl") or "").strip()
        jobs.append(
            normalize_job_payload(
                company=str(source.get("company_name") or company.replace("-", " ").title()),
                role=title,
                apply_link=apply_link,
                location=location,
                work_mode=infer_work_mode(location, title),
                category=infer_category(title),
                source_detail=f"lever:{company}",
                verification_notes=f"Live Lever board {company}",
            )
        )
    if not jobs:
        raise RuntimeError(f"No internship matches found on Lever board {company!r}.")
    return jobs
