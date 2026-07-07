from __future__ import annotations

import datetime as dt
import re
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

INTERN_KEYWORDS = ("intern", "internship", "trainee", "apprentice", "co-op", "co op")


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def clean_text(value: str) -> str:
    text = unescape(re.sub(r"\s+", " ", value or "")).strip()
    return text


def looks_like_intern(role: str, keywords: tuple[str, ...] = INTERN_KEYWORDS) -> bool:
    lowered = role.lower()
    return any(re.search(rf"\b{re.escape(keyword)}\b", lowered) for keyword in keywords)


def infer_category(role: str, default: str = "Other") -> str:
    lowered = role.lower()
    rules = (
        (("software", "engineer", "developer", "backend", "frontend", "devops", "qa", "sre"), "Software Engineering"),
        (("marketing", "seo", "content", "social media", "brand", "growth"), "Digital Marketing"),
        (("data", "analytics", "analyst", "bi ", "business intelligence", "scientist"), "Data Analytics"),
        (("hr", "human resources", "recruit", "people ops", "talent"), "HR"),
        (("finance", "account", "financial", "fp&a", "audit"), "Finance"),
        (("design", "ux", "ui", "product design"), "Design"),
        (("sales", "business development", "bdr", "sdr"), "Sales"),
        (("operations", "ops", "supply chain", "logistics"), "Operations"),
    )
    for terms, category in rules:
        if any(term in lowered for term in terms):
            return category
    return default


def infer_work_mode(location: str, role: str = "") -> str:
    combined = f"{location} {role}".lower()
    if "remote" in combined or "work from home" in combined or "wfh" in combined:
        return "Remote"
    if "hybrid" in combined:
        return "Hybrid"
    if location.strip():
        return "Onsite"
    return "Remote"


def default_last_date(days_ahead: int = 30) -> str:
    return (dt.date.today() + dt.timedelta(days=days_ahead)).isoformat()


def normalize_job_payload(
    *,
    company: str,
    role: str,
    apply_link: str,
    location: str = "Not listed",
    stipend: str = "Not listed",
    duration: str = "Not listed",
    work_mode: str | None = None,
    category: str | None = None,
    last_date: str | None = None,
    verified: bool = False,
    verification_notes: str = "Live scrape — pending manual verification",
    source_detail: str = "",
) -> dict[str, Any]:
    return {
        "company": clean_text(company),
        "role": clean_text(role),
        "category": category or infer_category(role),
        "location": clean_text(location) or "Not listed",
        "stipend": clean_text(stipend) or "Not listed",
        "work_mode": work_mode or infer_work_mode(location, role),
        "duration": clean_text(duration) or "Not listed",
        "apply_link": apply_link.strip(),
        "last_date": last_date or default_last_date(),
        "verified": verified,
        "verification_notes": verification_notes,
        "source_detail": source_detail,
    }


def strip_html(value: str) -> str:
    return clean_text(re.sub(r"<[^>]+>", " ", value or ""))
