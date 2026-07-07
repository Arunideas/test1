#!/usr/bin/env python3
"""Post a sample message to a LinkedIn company page.

The agent is dependency-free so it can run in this sample repository without
package manager setup. It defaults to a dry run; pass --post when you are ready
to publish a live company page update.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_MESSAGE = "Testing LinkedIn company page automation from my agent."
LINKEDIN_UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"


@dataclass(frozen=True)
class LinkedInConfig:
    """Configuration required to post as a LinkedIn organization."""

    access_token: str
    organization_id: str
    endpoint: str = LINKEDIN_UGC_POSTS_URL
    timeout_seconds: float = 30.0

    @property
    def author_urn(self) -> str:
        organization_id = self.organization_id.strip()
        if not organization_id:
            raise ValueError("LinkedIn organization ID cannot be empty.")
        if organization_id.startswith("urn:li:organization:"):
            return organization_id
        return f"urn:li:organization:{organization_id}"


class LinkedInCompanyPageAgent:
    """Builds and publishes simple text-only LinkedIn company page posts."""

    def __init__(self, config: LinkedInConfig):
        self.config = config

    def build_post_payload(self, message: str) -> dict[str, Any]:
        text = message.strip()
        if not text:
            raise ValueError("LinkedIn post message cannot be empty.")

        return {
            "author": self.config.author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                },
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
            },
        }

    def post_message(self, message: str) -> dict[str, Any]:
        if not self.config.access_token:
            raise ValueError("LINKEDIN_ACCESS_TOKEN is required to publish a post.")

        payload = self.build_post_payload(message)
        request = urllib.request.Request(
            self.config.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout_seconds,
            ) as response:
                response_body = response.read().decode("utf-8", errors="replace")
                return {
                    "status": response.status,
                    "headers": dict(response.headers.items()),
                    "body": _parse_json_response(response_body),
                }
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"LinkedIn API returned HTTP {error.code}: {error_body}"
            ) from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"Could not reach LinkedIn API: {error.reason}") from error


def _parse_json_response(response_body: str) -> Any:
    if not response_body:
        return None
    try:
        return json.loads(response_body)
    except json.JSONDecodeError:
        return response_body


def _load_config_from_env(args: argparse.Namespace) -> LinkedInConfig:
    access_token = args.access_token or os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    organization_id = args.organization_id or os.getenv("LINKEDIN_ORGANIZATION_ID", "")

    missing = []
    if not access_token.strip():
        missing.append("LINKEDIN_ACCESS_TOKEN")
    if not organization_id.strip():
        missing.append("LINKEDIN_ORGANIZATION_ID")
    if missing:
        raise ValueError(f"Missing required values: {', '.join(missing)}")

    return LinkedInConfig(
        access_token=access_token.strip(),
        organization_id=organization_id.strip(),
        endpoint=args.endpoint,
        timeout_seconds=args.timeout,
    )


def _build_dry_run_config(args: argparse.Namespace) -> LinkedInConfig:
    access_token = args.access_token or os.getenv(
        "LINKEDIN_ACCESS_TOKEN",
        "<set LINKEDIN_ACCESS_TOKEN>",
    )
    organization_id = args.organization_id or os.getenv(
        "LINKEDIN_ORGANIZATION_ID",
        "<set LINKEDIN_ORGANIZATION_ID>",
    )
    return LinkedInConfig(
        access_token=access_token,
        organization_id=organization_id,
        endpoint=args.endpoint,
        timeout_seconds=args.timeout,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Post a sample text update to a LinkedIn company page.",
    )
    parser.add_argument(
        "--message",
        default=os.getenv("LINKEDIN_SAMPLE_MESSAGE", DEFAULT_MESSAGE),
        help="Message text to post. Defaults to LINKEDIN_SAMPLE_MESSAGE or a test message.",
    )
    parser.add_argument(
        "--organization-id",
        help="LinkedIn organization ID or organization URN. Defaults to LINKEDIN_ORGANIZATION_ID.",
    )
    parser.add_argument(
        "--access-token",
        help="LinkedIn API access token. Defaults to LINKEDIN_ACCESS_TOKEN.",
    )
    parser.add_argument(
        "--endpoint",
        default=LINKEDIN_UGC_POSTS_URL,
        help=f"LinkedIn UGC Posts endpoint. Defaults to {LINKEDIN_UGC_POSTS_URL}.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Publish the message. Without this flag, the agent prints the payload only.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        if args.post:
            agent = LinkedInCompanyPageAgent(_load_config_from_env(args))
            result = agent.post_message(args.message)
            print("LinkedIn company page message posted successfully.")
            print(json.dumps(result, indent=2))
        else:
            agent = LinkedInCompanyPageAgent(_build_dry_run_config(args))
            payload = agent.build_post_payload(args.message)
            print("Dry run: no message was posted. Use --post to publish.")
            print(json.dumps(payload, indent=2))
    except (RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
