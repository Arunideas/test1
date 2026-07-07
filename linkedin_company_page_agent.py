#!/usr/bin/env python3
"""Post a sample message to a LinkedIn company page.

The script is intentionally dependency-free so it can run in this sample
repository without package manager setup. It defaults to a dry run to make
testing safe; pass --post when you are ready to publish.
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

    @property
    def author_urn(self) -> str:
        if self.organization_id.startswith("urn:li:organization:"):
            return self.organization_id
        return f"urn:li:organization:{self.organization_id}"


class LinkedInCompanyPageAgent:
    """Builds and publishes simple text-only LinkedIn company page posts."""

    def __init__(self, config: LinkedInConfig, endpoint: str = LINKEDIN_UGC_POSTS_URL):
        self.config = config
        self.endpoint = endpoint

    def build_post_payload(self, message: str) -> dict[str, Any]:
        return {
            "author": self.config.author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": message},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
            },
        }

    def post_message(self, message: str) -> dict[str, Any]:
        payload = self.build_post_payload(message)
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response_body = response.read().decode("utf-8")
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


def _load_config_from_env() -> LinkedInConfig:
    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
    organization_id = os.getenv("LINKEDIN_ORGANIZATION_ID", "").strip()

    missing = []
    if not access_token:
        missing.append("LINKEDIN_ACCESS_TOKEN")
    if not organization_id:
        missing.append("LINKEDIN_ORGANIZATION_ID")
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return LinkedInConfig(access_token=access_token, organization_id=organization_id)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Post a sample text update to a LinkedIn company page."
    )
    parser.add_argument(
        "--message",
        default=os.getenv("LINKEDIN_SAMPLE_MESSAGE", DEFAULT_MESSAGE),
        help="Message text to post. Defaults to LINKEDIN_SAMPLE_MESSAGE or a test message.",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Publish the message. Without this flag, the agent prints the payload only.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not args.message.strip():
        print("Message cannot be empty.", file=sys.stderr)
        return 2

    config = LinkedInConfig(
        access_token=os.getenv("LINKEDIN_ACCESS_TOKEN", "<set LINKEDIN_ACCESS_TOKEN>"),
        organization_id=os.getenv(
            "LINKEDIN_ORGANIZATION_ID", "<set LINKEDIN_ORGANIZATION_ID>"
        ),
    )
    agent = LinkedInCompanyPageAgent(config)
    payload = agent.build_post_payload(args.message.strip())

    if not args.post:
        print("Dry run: no message was posted. Use --post to publish.")
        print(json.dumps(payload, indent=2))
        return 0

    try:
        live_agent = LinkedInCompanyPageAgent(_load_config_from_env())
        result = live_agent.post_message(args.message.strip())
    except (RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    print("LinkedIn company page message posted successfully.")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
