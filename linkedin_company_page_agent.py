#!/usr/bin/env python3
"""Post a text update to LinkedIn.

The agent defaults to dry-run mode so the payload can be tested without
credentials. Pass --post with a valid access token and author id to send the
update to LinkedIn.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_MESSAGE = "Sample test post from the LinkedIn company page agent."
DEFAULT_API_BASE_URL = "https://api.linkedin.com"
DEFAULT_AUTHORIZATION_URL = "https://www.linkedin.com/oauth/v2/authorization"
DEFAULT_ORGANIZATION_OAUTH_SCOPES = ("w_organization_social", "r_organization_social")
DEFAULT_MEMBER_OAUTH_SCOPES = ("openid", "profile", "email", "w_member_social")
PLACEHOLDER_ORGANIZATION_URN = "urn:li:organization:YOUR_ORGANIZATION_ID"
PLACEHOLDER_MEMBER_URN = "urn:li:person:YOUR_MEMBER_ID"


class LinkedInPostError(RuntimeError):
    """Raised when LinkedIn rejects or cannot process a post request."""


@dataclass(frozen=True)
class LinkedInCompanyPageAgent:
    """Small agent for publishing text posts to LinkedIn."""

    organization_urn: str
    member_urn: str | None = None
    access_token: str | None = None
    api_base_url: str = DEFAULT_API_BASE_URL
    timeout_seconds: int = 30

    @classmethod
    def from_environment(cls) -> "LinkedInCompanyPageAgent":
        organization_urn = normalize_organization_urn(
            os.getenv("LINKEDIN_ORGANIZATION_URN"),
            os.getenv("LINKEDIN_ORGANIZATION_ID"),
        )
        member_urn = normalize_member_urn(
            os.getenv("LINKEDIN_MEMBER_URN"),
            os.getenv("LINKEDIN_MEMBER_ID"),
        )
        return cls(
            organization_urn=organization_urn or PLACEHOLDER_ORGANIZATION_URN,
            member_urn=member_urn,
            access_token=os.getenv("LINKEDIN_ACCESS_TOKEN"),
            api_base_url=os.getenv("LINKEDIN_API_BASE_URL", DEFAULT_API_BASE_URL),
        )

    def build_text_post_payload(
        self,
        message: str,
        *,
        author_urn: str | None = None,
    ) -> dict[str, Any]:
        message = message.strip()
        if not message:
            raise ValueError("Message cannot be empty.")

        return {
            "author": author_urn or self.organization_urn,
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

    def post_text(
        self,
        message: str,
        *,
        dry_run: bool = True,
        post_as: str = "organization",
    ) -> dict[str, Any]:
        author_urn = self.author_urn_for(post_as)
        payload = self.build_text_post_payload(message, author_urn=author_urn)

        if dry_run:
            return {
                "dry_run": True,
                "post_as": post_as,
                "endpoint": self.post_endpoint,
                "payload": payload,
                "note": "No request was sent. Run with --post to publish.",
            }

        self._validate_publish_configuration(post_as)
        return self._send_post(payload)

    def author_urn_for(self, post_as: str) -> str:
        if post_as == "organization":
            return self.organization_urn
        if post_as == "member":
            return self.member_urn or PLACEHOLDER_MEMBER_URN
        raise ValueError("post_as must be either 'organization' or 'member'.")

    @property
    def post_endpoint(self) -> str:
        return f"{self.api_base_url.rstrip('/')}/v2/ugcPosts"

    def _validate_publish_configuration(self, post_as: str) -> None:
        if not self.access_token:
            raise ValueError("LINKEDIN_ACCESS_TOKEN is required when using --post.")
        if post_as == "organization" and self.organization_urn == PLACEHOLDER_ORGANIZATION_URN:
            raise ValueError(
                "LINKEDIN_ORGANIZATION_ID or LINKEDIN_ORGANIZATION_URN is required "
                "when using --post."
            )
        if post_as == "member" and not self.member_urn:
            raise ValueError(
                "LINKEDIN_MEMBER_ID or LINKEDIN_MEMBER_URN is required when posting "
                "as a member. Use the authenticated member id from LinkedIn."
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


def normalize_member_urn(
    member_urn: str | None,
    member_id: str | None,
) -> str | None:
    if member_urn:
        return member_urn.strip()
    if member_id:
        return f"urn:li:person:{member_id.strip()}"
    return None


def build_authorization_url(
    *,
    client_id: str,
    redirect_uri: str,
    scopes: list[str],
    state: str,
    authorization_url: str = DEFAULT_AUTHORIZATION_URL,
) -> str:
    client_id = client_id.strip()
    redirect_uri = redirect_uri.strip()
    state = state.strip()

    if not client_id:
        raise ValueError("LINKEDIN_CLIENT_ID or --client-id is required.")
    if not redirect_uri:
        raise ValueError("LINKEDIN_REDIRECT_URI or --redirect-uri is required.")
    if not scopes:
        raise ValueError("At least one OAuth scope is required.")
    if not state:
        raise ValueError("OAuth state cannot be empty.")

    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
        },
        quote_via=urllib.parse.quote,
    )
    return f"{authorization_url}?{query}"


def normalize_scopes(
    scopes: list[str] | None,
    scopes_from_env: str | None,
    *,
    post_as: str,
) -> list[str]:
    if scopes:
        raw_scopes = scopes
    elif scopes_from_env:
        raw_scopes = scopes_from_env.replace(",", " ").split()
    elif post_as == "member":
        raw_scopes = list(DEFAULT_MEMBER_OAUTH_SCOPES)
    else:
        raw_scopes = list(DEFAULT_ORGANIZATION_OAUTH_SCOPES)

    normalized_scopes: list[str] = []
    for scope in raw_scopes:
        for item in scope.replace(",", " ").split():
            item = item.strip()
            if item and item not in normalized_scopes:
                normalized_scopes.append(item)
    return normalized_scopes


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
        "--member-id",
        help="LinkedIn authenticated member id. Overrides LINKEDIN_MEMBER_ID.",
    )
    parser.add_argument(
        "--member-urn",
        help="Full LinkedIn member/person URN. Overrides LINKEDIN_MEMBER_URN.",
    )
    parser.add_argument(
        "--post-as",
        choices=("organization", "member"),
        default=os.getenv("LINKEDIN_POST_AS", "organization"),
        help=(
            "Author type for auth URL generation and posting. Use 'member' for "
            "personal profile posts with w_member_social."
        ),
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="Actually publish the update. Omit this flag for a dry run.",
    )
    parser.add_argument(
        "--auth-url",
        action="store_true",
        help="Generate the LinkedIn browser authorization URL and exit.",
    )
    parser.add_argument(
        "--client-id",
        default=os.getenv("LINKEDIN_CLIENT_ID"),
        help="LinkedIn app client id. Defaults to LINKEDIN_CLIENT_ID.",
    )
    parser.add_argument(
        "--redirect-uri",
        default=os.getenv("LINKEDIN_REDIRECT_URI"),
        help="OAuth redirect URI registered in LinkedIn. Defaults to LINKEDIN_REDIRECT_URI.",
    )
    parser.add_argument(
        "--scope",
        action="append",
        help=(
            "OAuth scope to request. May be passed multiple times or as a "
            "space/comma-separated value. Defaults to organization posting scopes."
        ),
    )
    parser.add_argument(
        "--state",
        default=os.getenv("LINKEDIN_OAUTH_STATE"),
        help="OAuth state value. Defaults to a generated random value.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    if args.auth_url:
        state = args.state or secrets.token_urlsafe(24)
        scopes = normalize_scopes(
            args.scope,
            os.getenv("LINKEDIN_OAUTH_SCOPES"),
            post_as=args.post_as,
        )
        try:
            authorization_url = build_authorization_url(
                client_id=args.client_id or "",
                redirect_uri=args.redirect_uri or "",
                scopes=scopes,
                state=state,
            )
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1

        print(
            json.dumps(
                {
                    "authorization_url": authorization_url,
                    "post_as": args.post_as,
                    "state": state,
                    "scopes": scopes,
                    "next_step": (
                        "Open authorization_url in a browser, approve access, "
                        "then copy the code query parameter from the redirect URL."
                    ),
                },
                indent=2,
            )
        )
        return 0

    agent = LinkedInCompanyPageAgent.from_environment()

    organization_urn = normalize_organization_urn(args.organization_urn, args.organization_id)
    member_urn = normalize_member_urn(args.member_urn, args.member_id)
    if organization_urn:
        agent = LinkedInCompanyPageAgent(
            organization_urn=organization_urn,
            member_urn=member_urn or agent.member_urn,
            access_token=args.access_token or agent.access_token,
            api_base_url=agent.api_base_url,
            timeout_seconds=agent.timeout_seconds,
        )
    elif member_urn or args.access_token:
        agent = LinkedInCompanyPageAgent(
            organization_urn=agent.organization_urn,
            member_urn=member_urn or agent.member_urn,
            access_token=args.access_token or agent.access_token,
            api_base_url=agent.api_base_url,
            timeout_seconds=agent.timeout_seconds,
        )

    try:
        result = agent.post_text(args.message, dry_run=not args.post, post_as=args.post_as)
    except (LinkedInPostError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
