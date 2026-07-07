from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.parse import quote_plus

from internship_collectors.http_utils import fetch_text
from internship_collectors.utils import (
    infer_category,
    infer_work_mode,
    normalize_job_payload,
    strip_html,
)

LINKEDIN_GUEST_SEARCH_URL = (
    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
)


def _parse_linkedin_cards(html: str) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    blocks = re.findall(r"<li>[\s\S]*?job-search-card[\s\S]*?</li>", html, flags=re.IGNORECASE)
    for block in blocks:
        link_match = re.search(
            r'base-card__full-link[^>]+href="(?P<href>[^"]+)"',
            block,
            flags=re.IGNORECASE,
        )
        title_match = re.search(
            r'base-search-card__title">\s*(?P<title>[\s\S]*?)\s*</h3>',
            block,
            flags=re.IGNORECASE,
        )
        company_match = re.search(
            r"hidden-nested-link[^>]*>\s*(?P<company>[\s\S]*?)\s*</a>",
            block,
            flags=re.IGNORECASE,
        )
        location_match = re.search(
            r'job-search-card__location">\s*(?P<location>[\s\S]*?)\s*</span>',
            block,
            flags=re.IGNORECASE,
        )
        if not link_match or not title_match:
            continue
        cards.append(
            {
                "title": strip_html(title_match.group("title")),
                "apply_link": unescape(link_match.group("href")),
                "company": strip_html(company_match.group("company")) if company_match else "Unknown company",
                "location": strip_html(location_match.group("location")) if location_match else "Not listed",
            }
        )
    return cards


def collect_linkedin_search(source: dict[str, Any]) -> list[dict[str, Any]]:
    keywords = str(source.get("keywords") or "internship").strip()
    location = str(source.get("location") or "India").strip()
    pages = max(1, min(int(source.get("pages") or 2), 10))
    count = max(10, min(int(source.get("count") or 25), 25))
    jobs: list[dict[str, Any]] = []
    seen_links: set[str] = set()

    for page in range(pages):
        start = page * count
        query = (
            f"{LINKEDIN_GUEST_SEARCH_URL}"
            f"?keywords={quote_plus(keywords)}"
            f"&location={quote_plus(location)}"
            f"&start={start}&count={count}"
        )
        html = fetch_text(
            query,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        cards = _parse_linkedin_cards(html)
        if not cards and page == 0:
            raise RuntimeError(
                "LinkedIn guest search returned no parseable job cards. "
                "The page layout may have changed or access may be blocked."
            )
        for card in cards:
            link = card["apply_link"]
            if link in seen_links:
                continue
            seen_links.add(link)
            title = card["title"]
            jobs.append(
                normalize_job_payload(
                    company=card["company"],
                    role=title,
                    apply_link=link,
                    location=card["location"],
                    work_mode=infer_work_mode(card["location"], title),
                    category=infer_category(title),
                    source_detail=f"linkedin_search:{keywords}:{location}",
                    verification_notes="Live LinkedIn search result — verify company and role before applying",
                )
            )
        if not cards:
            break
    if not jobs:
        raise RuntimeError(
            f"No LinkedIn internship results found for keywords={keywords!r} location={location!r}."
        )
    return jobs
