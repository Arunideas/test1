#!/usr/bin/env python3
"""Post a text update to a LinkedIn company page.

The agent defaults to dry-run mode so the payload can be tested without
credentials. Pass --post with a valid access token and organization id to send
the update to LinkedIn.
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


DEFAULT_MESSAGE = "Sample test post from the LinkedIn company page agent."
DEFAULT_API_BASE_URL = "https://api.linkedin.com"
PLACEHOLDER_ORGANIZATION_URN = "urn:li:organization:YOUR_ORGANIZATION_ID"


class LinkedInPostError(RuntimeError):
    """Raised when LinkedIn rejects or cannot process a post request."""


@dataclass(frozen=True)
class LinkedInCompanyPageAgent:
    """Small agent for publishing text posts to a LinkedIn organization page."""

    organization_urn: str
    access_token: str | None = None
    api_base_url: str = DEFAULT_API_BASE_URL
    timeout_seconds: int = 30

    @classmethod
    def from_environment(cls) -> "LinkedInCompanyPageAgent":
        organization_urn = normalize_organization_urn(
            os.getenv("LINKEDIN_ORGANIZATION_URN"),
            os.getenv("LINKEDIN_ORGANIZATION_ID"),
        )
        return cls(
            organization_urn=organization_urn or PLACEHOLDER_ORGANIZATION_URN,
            access_token=os.getenv("LINKEDIN_ACCESS_TOKEN"),
            api_base_url=os.getenv("LINKEDIN_API_BASE_URL", DEFAULT_API_BASE_URL),
        )

    def build_text_post_payload(self, message: str) -> dict[str, Any]:
        message = message.strip()
        if not message:
            raise ValueError("Message cannot be empty.")

        return {
            "author": self.organization_urn,
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

    def post_text(self, message: str, *, dry_run: bool = True) -> dict[str, Any]:
        payload = self.build_text_post_payload(message)

        if dry_run:
            return {
                "dry_run": True,
                "endpoint": self.post_endpoint,
                "payload": payload,
                "note": "No request was sent. Run with --post to publish.",
            }

        self._validate_publish_configuration()
        return self._send_post(payload)

    @property
    def post_endpoint(self) -> str:
        return f"{self.api_base_url.rstrip('/')}/v2/ugcPosts"

    def _validate_publish_configuration(self) -> None:
        if not self.access_token:
            raise ValueError("LINKEDIN_ACCESS_TOKEN is required when using --post.")
        if self.organization_urn == PLACEHOLDER_ORGANIZATION_URN:
            raise ValueError(
                "LINKEDIN_ORGANIZATION_ID or LINKEDIN_ORGANIZATION_URN is required "
                "when using --post."
            )

    def _send_post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.post_endpoint,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            error_body = error.read().decode("utf-8", errors="replace")
            raise LinkedInPostError(
                f"LinkedIn API returned HTTP {error.code}: {error_body}"
            ) from error
        except urllib.error.URLError as error:
            raise LinkedInPostError(f"Unable to reach LinkedIn API: {error.reason}") from error

        parsed_body: Any
        if response_body:
            try:
                parsed_body = json.loads(response_body)
            except json.JSONDecodeError:
                parsed_body = response_body
        else:
            parsed_body = {}

        return {
            "dry_run": False,
            "endpoint": self.post_endpoint,
            "response": parsed_body,
        }


def normalize_organization_urn(
    organization_urn: str | None,
    organization_id: str | None,
) -> str | None:
    if organization_urn:
        return organization_urn.strip()
    if organization_id:
        return f"urn:li:organization:{organization_id.strip()}"
    return None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Post a sample text message to a LinkedIn company page.",
    )
    parser.add_argument(
        "--message",
        default=os.getenv("LINKEDIN_POST_MESSAGE", DEFAULT_MESSAGE),
        help="Message text to publish. Defaults to a sample testing message.",
    )
    parser.add_argument(
        "--organization-id",
        help="LinkedIn organization id. Overrides LINKEDIN_ORGANIZATION_ID.",
    )
    parser.add_argument(
        "--organization-urn",
        help="Full LinkedIn organization URN. Overrides LINKEDIN_ORGANIZATION_URN.",
    )
    parser.add_argument(
        "--access-token",
        help="LinkedIn API access token. Overrides LINKEDIN_ACCESS_TOKEN.",
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Actually publish the update. Omit this flag for a dry run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    agent = LinkedInCompanyPageAgent.from_environment()

    organization_urn = normalize_organization_urn(args.organization_urn, args.organization_id)
    if organization_urn:
        agent = LinkedInCompanyPageAgent(
            organization_urn=organization_urn,
            access_token=args.access_token or agent.access_token,
            api_base_url=agent.api_base_url,
            timeout_seconds=agent.timeout_seconds,
        )
    elif args.access_token:
        agent = LinkedInCompanyPageAgent(
            organization_urn=agent.organization_urn,
            access_token=args.access_token,
            api_base_url=agent.api_base_url,
            timeout_seconds=agent.timeout_seconds,
        )

    try:
        result = agent.post_text(args.message, dry_run=not args.post)
    except (LinkedInPostError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
