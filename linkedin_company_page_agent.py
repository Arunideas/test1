#!/usr/bin/env python3
"""Post a sample text update to a LinkedIn company page.

The agent intentionally uses only the Python standard library so it can run in
this small repository without installing dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping, Sequence


DEFAULT_API_URL = "https://api.linkedin.com/v2/ugcPosts"
DEFAULT_MESSAGE = (
    "This is a sample company page test post from the LinkedIn Company Page Agent."
)
USER_AGENT = "linkedin-company-page-agent/1.0"


@dataclass(frozen=True)
class LinkedInConfig:
    """Runtime settings needed to post to a LinkedIn organization page."""

    organization_id: str
    access_token: str | None
    api_url: str = DEFAULT_API_URL
    timeout: float = 30.0

    @property
    def organization_urn(self) -> str:
        return organization_urn(self.organization_id)


@dataclass(frozen=True)
class LinkedInPostResult:
    """Small response object returned after LinkedIn accepts a post request."""

    status_code: int
    location: str | None
    body: str


def organization_urn(organization_id: str) -> str:
    """Return a LinkedIn organization URN from either an ID or an existing URN."""

    cleaned = organization_id.strip()
    if not cleaned:
        raise ValueError("LinkedIn organization ID cannot be empty.")
    if cleaned.startswith("urn:li:organization:"):
        return cleaned
    return f"urn:li:organization:{cleaned}"


def build_post_payload(organization_id: str, message: str) -> dict[str, object]:
    """Build the LinkedIn UGC post payload for a text-only company page update."""

    text = message.strip()
    if not text:
        raise ValueError("LinkedIn post message cannot be empty.")

    return {
        "author": organization_urn(organization_id),
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": text,
                },
                "shareMediaCategory": "NONE",
            },
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
        },
    }


def _decode_response_body(raw_body: bytes) -> str:
    return raw_body.decode("utf-8", errors="replace")


def post_to_linkedin(
    config: LinkedInConfig,
    message: str,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> LinkedInPostResult:
    """Send a text-only company page update to LinkedIn."""

    if not config.access_token:
        raise ValueError("LINKEDIN_ACCESS_TOKEN is required to publish a post.")

    payload = build_post_payload(config.organization_id, message)
    request = urllib.request.Request(
        config.api_url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {config.access_token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "X-Restli-Protocol-Version": "2.0.0",
        },
    )

    try:
        with opener(request, timeout=config.timeout) as response:
            body = _decode_response_body(response.read())
            return LinkedInPostResult(
                status_code=getattr(response, "status", 201),
                location=response.headers.get("Location"),
                body=body,
            )
    except urllib.error.HTTPError as exc:
        body = _decode_response_body(exc.read())
        raise RuntimeError(f"LinkedIn API returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach LinkedIn API: {exc.reason}") from exc


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Post a sample text update to a LinkedIn company page.",
    )
    parser.add_argument(
        "--message",
        default=DEFAULT_MESSAGE,
        help="Message to publish. Defaults to a safe sample test message.",
    )
    parser.add_argument(
        "--organization-id",
        help=(
            "LinkedIn organization ID or organization URN. "
            "Defaults to LINKEDIN_ORGANIZATION_ID."
        ),
    )
    parser.add_argument(
        "--access-token",
        help="LinkedIn API access token. Defaults to LINKEDIN_ACCESS_TOKEN.",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"LinkedIn UGC Posts endpoint. Defaults to {DEFAULT_API_URL}.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the LinkedIn payload without sending it.",
    )
    return parser


def config_from_args(
    args: argparse.Namespace,
    env: Mapping[str, str] | None = None,
) -> LinkedInConfig:
    source_env = os.environ if env is None else env
    organization_id = args.organization_id or source_env.get("LINKEDIN_ORGANIZATION_ID")
    access_token = args.access_token or source_env.get("LINKEDIN_ACCESS_TOKEN")

    if not organization_id:
        raise ValueError(
            "LinkedIn organization ID is required. Set LINKEDIN_ORGANIZATION_ID "
            "or pass --organization-id."
        )

    return LinkedInConfig(
        organization_id=organization_id,
        access_token=access_token,
        api_url=args.api_url,
        timeout=args.timeout,
    )


def main(
    argv: Sequence[str] | None = None,
    env: Mapping[str, str] | None = None,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        config = config_from_args(args, env)
        if args.dry_run:
            payload = build_post_payload(config.organization_id, args.message)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0

        result = post_to_linkedin(config, args.message, opener=opener)
    except ValueError as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"Post failed: {exc}", file=sys.stderr)
        return 1

    print(f"LinkedIn post created successfully with HTTP status {result.status_code}.")
    if result.location:
        print(f"Location: {result.location}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
