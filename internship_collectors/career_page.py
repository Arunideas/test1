from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from internship_collectors.http_utils import fetch_text
from internship_collectors.utils import (
    infer_category,
    infer_work_mode,
    looks_like_intern,
    normalize_job_payload,
)


class CareerLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._current_href = href
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return
        text = " ".join(part.strip() for part in self._current_text if part.strip())
        if text:
            self.links.append((self._current_href, text))
        self._current_href = None
        self._current_text = []


def collect_career_page(source: dict[str, Any]) -> list[dict[str, Any]]:
    page_url = str(source["url"]).strip()
    company_name = str(source.get("company_name") or urlparse(page_url).netloc).strip()
    link_keywords = tuple(
        keyword.lower()
        for keyword in source.get("link_keywords") or ("intern", "internship", "early career")
    )
    role_pattern = source.get("role_pattern")
    parser = CareerLinkParser()
    html = fetch_text(page_url)
    parser.feed(html)
    jobs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for href, text in parser.links:
        absolute = urljoin(page_url, href)
        if absolute in seen:
            continue
        lowered = f"{text} {absolute}".lower()
        if role_pattern:
            if not re.search(str(role_pattern), lowered, flags=re.IGNORECASE):
                continue
        elif not any(keyword in lowered for keyword in link_keywords):
            continue
        if not looks_like_intern(text) and not any(keyword in lowered for keyword in link_keywords):
            continue
        seen.add(absolute)
        jobs.append(
            normalize_job_payload(
                company=company_name,
                role=text,
                apply_link=absolute,
                location=str(source.get("location_default") or "Not listed"),
                work_mode=infer_work_mode(str(source.get("location_default") or ""), text),
                category=infer_category(text),
                source_detail=f"career_page:{page_url}",
                verification_notes=f"Live career page scrape from {page_url}",
            )
        )
    if not jobs:
        raise RuntimeError(f"No internship-like links found on career page {page_url!r}.")
    return jobs
