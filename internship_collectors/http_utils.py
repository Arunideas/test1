from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; WorldOfInternsCollector/1.0; "
        "+https://github.com/Arunideas/test1)"
    ),
    "Accept": "application/json,text/html,*/*",
}


def fetch_text(url: str, *, timeout: int = 30, headers: dict[str, str] | None = None) -> str:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={**DEFAULT_HEADERS, **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code} for {url}: {body[:500]}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Unable to reach {url}: {error.reason}") from error


def fetch_json(url: str, *, timeout: int = 30, headers: dict[str, str] | None = None) -> Any:
    return json.loads(fetch_text(url, timeout=timeout, headers=headers))
