from __future__ import annotations

from typing import Any

from internship_collectors.http_utils import fetch_json
from internship_collectors.utils import (
    default_last_date,
    infer_work_mode,
    looks_like_intern,
    normalize_job_payload,
    strip_html,
)


def collect_greenhouse(source: dict[str, Any]) -> list[dict[str, Any]]:
    board = str(source["board"]).strip()
    source_name = str(source.get("source_name") or f"greenhouse_{board}")
    category_default = str(source.get("category_default") or "Other")
    keywords = tuple(source.get("keywords") or ("intern", "internship"))
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    payload = fetch_json(url)
    jobs: list[dict[str, Any]] = []
    for item in payload.get("jobs", []):
        title = str(item.get("title", "")).strip()
        if not title or not looks_like_intern(title, keywords):
            continue
        location = "Not listed"
        offices = item.get("offices") or []
        if offices:
            location = ", ".join(
                str(office.get("name", "")).strip()
                for office in offices
                if office.get("name")
            ) or location
        metadata = item.get("metadata") or []
        stipend = "Not listed"
        for entry in metadata:
            name = str(entry.get("name", "")).lower()
            if any(token in name for token in ("pay", "salary", "compensation", "stipend")):
                stipend = str(entry.get("value") or "Not listed")
                break
        jobs.append(
            normalize_job_payload(
                company=str(source.get("company_name") or board.replace("-", " ").title()),
                role=title,
                apply_link=str(item.get("absolute_url") or item.get("url") or "").strip(),
                location=location,
                stipend=strip_html(stipend),
                work_mode=infer_work_mode(location, title),
                category=category_default,
                last_date=default_last_date(),
                source_detail=f"greenhouse:{board}",
                verification_notes=f"Live Greenhouse board {board}",
            )
        )
    if not jobs:
        raise RuntimeError(f"No internship matches found on Greenhouse board {board!r}.")
    return jobs
