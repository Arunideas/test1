import contextlib
import io
import json
import unittest

import linkedin_company_page_agent as agent


class FakeResponse:
    def __init__(self, body=b"", status=201, headers=None):
        self._body = body
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self._body


class LinkedInCompanyPageAgentTests(unittest.TestCase):
    def test_build_post_payload_creates_text_only_company_page_update(self):
        payload = agent.build_post_payload("123456", "  Hello LinkedIn  ")

        self.assertEqual(payload["author"], "urn:li:organization:123456")
        self.assertEqual(payload["lifecycleState"], "PUBLISHED")
        self.assertEqual(
            payload["specificContent"]["com.linkedin.ugc.ShareContent"][
                "shareCommentary"
            ]["text"],
            "Hello LinkedIn",
        )
        self.assertEqual(
            payload["specificContent"]["com.linkedin.ugc.ShareContent"][
                "shareMediaCategory"
            ],
            "NONE",
        )
        self.assertEqual(
            payload["visibility"]["com.linkedin.ugc.MemberNetworkVisibility"],
            "PUBLIC",
        )

    def test_build_post_payload_accepts_existing_organization_urn(self):
        payload = agent.build_post_payload(
            "urn:li:organization:987654",
            agent.DEFAULT_MESSAGE,
        )

        self.assertEqual(payload["author"], "urn:li:organization:987654")

    def test_dry_run_prints_payload_without_access_token(self):
        stdout = io.StringIO()

        with contextlib.redirect_stdout(stdout):
            exit_code = agent.main(
                ["--organization-id", "123456", "--message", "Dry run", "--dry-run"],
                env={},
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["author"], "urn:li:organization:123456")
        self.assertEqual(
            payload["specificContent"]["com.linkedin.ugc.ShareContent"][
                "shareCommentary"
            ]["text"],
            "Dry run",
        )

    def test_publish_requires_access_token(self):
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            exit_code = agent.main(["--organization-id", "123456"], env={})

        self.assertEqual(exit_code, 2)
        self.assertIn("LINKEDIN_ACCESS_TOKEN is required", stderr.getvalue())

    def test_post_to_linkedin_sends_expected_request(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["headers"] = dict(request.header_items())
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["method"] = request.get_method()
            return FakeResponse(headers={"Location": "urn:li:share:abc"})

        config = agent.LinkedInConfig(
            organization_id="123456",
            access_token="token-value",
            timeout=3.0,
        )
        result = agent.post_to_linkedin(config, "Request test", opener=opener)

        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.location, "urn:li:share:abc")
        self.assertEqual(captured["url"], agent.DEFAULT_API_URL)
        self.assertEqual(captured["timeout"], 3.0)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer token-value")
        self.assertEqual(captured["headers"]["Content-type"], "application/json")
        self.assertEqual(
            captured["headers"]["X-restli-protocol-version"],
            "2.0.0",
        )
        self.assertEqual(captured["payload"]["author"], "urn:li:organization:123456")


if __name__ == "__main__":
    unittest.main()
